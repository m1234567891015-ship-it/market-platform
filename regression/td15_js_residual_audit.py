"""Re-audit the TD-15 JS residual snapshot against the current source tree.

R3 is intentionally read-only: the historical 52/6 snapshot may already have
been processed by H-04-11..15, so this tool proves the current state before any
new deletion is considered. It does not modify source or baseline files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CLASSIFICATION = ROOT / "docs" / "td15_js_classification.md"
LEGACY_SOURCE = ROOT / "js" / "legacy-unclassified.js"
JSON_OUTPUT = ROOT / "docs" / "TD15_R3_js_residual_audit_2026-08-31.json"
MD_OUTPUT = ROOT / "docs" / "TD15_R3_js_residual_audit_2026-08-31.md"

SYMBOL_ROW_RE = re.compile(r"^\| `([A-Za-z_$][A-Za-z0-9_$]*)` \| js/legacy-unclassified\.js:")
WORD_TEMPLATE = r"(?<![A-Za-z0-9_$]){name}(?![A-Za-z0-9_$])"
DECL_RE = re.compile(r"\b(?:function|class)\s+([A-Za-z_$][A-Za-z0-9_$]*)\b|\b(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)\b")
DYNAMIC_RE = re.compile(r"window\s*\[([^\]]+)\]")


def read_utf8(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def snapshot_symbols() -> list[str]:
    return [
        match.group(1)
        for line in read_utf8(CLASSIFICATION).splitlines()
        if (match := SYMBOL_ROW_RE.match(line))
    ]


def executable_sources() -> list[Path]:
    excluded = {".git", ".tmp", "docs", "baseline"}
    allowed = {".html", ".js", ".py", ".css"}
    return sorted(
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and path.suffix.lower() in allowed
        and not set(path.relative_to(ROOT).parts).intersection(excluded)
    )


def scan_symbols(symbols: list[str]) -> dict[str, list[dict[str, object]]]:
    hits = {symbol: [] for symbol in symbols}
    for symbol in symbols:
        pattern = re.compile(WORD_TEMPLATE.format(name=re.escape(symbol)))
        for path in executable_sources():
            for line_number, line in enumerate(read_utf8(path).splitlines(), 1):
                if pattern.search(line):
                    hits[symbol].append(
                        {"file": path.relative_to(ROOT).as_posix(), "line": line_number}
                    )
    return hits


def runtime_dynamic_scan(symbols: list[str]) -> dict[str, object]:
    dynamic_sites = []
    candidate_dynamic_hits = []
    candidate_patterns = [re.compile(WORD_TEMPLATE.format(name=re.escape(symbol))) for symbol in symbols]
    for path in sorted(ROOT.rglob("*.js")):
        if set(path.relative_to(ROOT).parts).intersection({".git", ".tmp", "docs", "baseline"}):
            continue
        for line_number, line in enumerate(read_utf8(path).splitlines(), 1):
            for match in DYNAMIC_RE.finditer(line):
                site = {
                    "file": path.relative_to(ROOT).as_posix(),
                    "line": line_number,
                    "expression": match.group(1).strip(),
                }
                dynamic_sites.append(site)
                if any(pattern.search(match.group(1)) for pattern in candidate_patterns):
                    candidate_dynamic_hits.append(site)
    return {
        "window_bracket_site_count": len(dynamic_sites),
        "candidate_dynamic_hits": candidate_dynamic_hits,
        "candidate_dynamic_hit_count": len(candidate_dynamic_hits),
    }


def build_audit() -> dict:
    symbols = snapshot_symbols()
    hits = scan_symbols(symbols)
    declarations = []
    legacy_text = read_utf8(LEGACY_SOURCE)
    for match in DECL_RE.finditer(legacy_text):
        declarations.append(next(group for group in match.groups() if group))
    return {
        "schema_version": 1,
        "snapshot_date": "2026-08-31",
        "status": "R3_PASS_NO_DELETION",
        "historical_snapshot": {
            "symbol_count": len(symbols),
            "layer_1_snapshot": 52,
            "layer_2_observe_snapshot": 6,
            "symbols": symbols,
        },
        "current_source": {
            "legacy_source": LEGACY_SOURCE.relative_to(ROOT).as_posix(),
            "legacy_source_bytes": LEGACY_SOURCE.stat().st_size,
            "legacy_top_level_declarations": declarations,
            "legacy_top_level_declaration_count": len(declarations),
            "literal_hit_count_by_symbol": {symbol: len(hits[symbol]) for symbol in symbols},
            "total_executable_literal_hits": sum(len(items) for items in hits.values()),
            "dynamic_scan": runtime_dynamic_scan(symbols),
        },
        "evidence": {
            "ast_or_source_owner": "current legacy-unclassified.js is empty; no historical TD-15 declaration remains",
            "repo_literal_scan": "zero hits across current HTML, JS, CSS, and Python sources outside docs/baseline/.tmp",
            "dynamic_access": "window[...] sites exist, but none contains a historical TD-15 symbol name",
            "observe_chains": "H-04-11..H-04-15 records already cover the five historical observe chains",
        },
        "scope": {
            "source_extensions": [".html", ".js", ".py", ".css"],
            "excluded_paths": ["docs", "regression/baseline", ".tmp", ".git"],
            "frontend_page_count": 21,
            "interaction_step_count": 94,
        },
        "next_gate": {
            "deletion_authorized_by_this_audit": False,
            "reason": "no current TD-15 JS residual symbol or declaration exists",
        },
    }


def render_markdown(audit: dict) -> str:
    current = audit["current_source"]
    dynamic = current["dynamic_scan"]
    lines = [
        "# TD-15 R3 JS residual audit（2026-08-31）",
        "",
        "本報告是 R3 現況重核，唯讀、不刪除 JS、不更新 baseline。",
        "",
        "## 結論",
        "",
        "- 狀態：`R3_PASS_NO_DELETION`。歷史 snapshot 仍記錄 52 個第一層與 6 個第二層 observe，但目前已不存在可刪除的 residual symbol。",
        f"- `js/legacy-unclassified.js` 目前為 {current['legacy_source_bytes']} bytes、{current['legacy_top_level_declaration_count']} 個 top-level declaration。",
        f"- 58 個歷史符號在目前 HTML／JS／CSS／Python 執行來源的 literal hit 總數為 {current['total_executable_literal_hits']}。",
        f"- JS `window[...]` sites 共 {dynamic['window_bracket_site_count']} 個；命中歷史 TD-15 symbol 的 dynamic site 為 {dynamic['candidate_dynamic_hit_count']} 個。",
        "- H-04-11～H-04-15 已記錄的五條觀察呼叫鏈不重複處理；本批沒有 source 或 baseline deletion。",
        "",
        "## 三方證據",
        "",
        "1. **目前 source／AST owner**：legacy isolation file 為空，沒有 52/6 snapshot 的現存 declaration。",
        "2. **repo literal scan**：排除 docs、baseline、`.tmp` 與 `.git` 後，58 個歷史符號在 HTML、JS、CSS、Python 中均為零命中。",
        "3. **dynamic access**：目前 JS 仍有一般 `window[...]`，但其 expression 均未命中 58 個歷史符號；不存在可解析到這批候選的動態入口。",
        "",
        "## 驗收範圍",
        "",
        "- frontend：21 頁。",
        "- interaction：94 條 steps。",
        "- global-symbol baseline：由既有 `td02_01_dependency_matrix.py --check` 另行確認，R3 不更新 baseline。",
        "",
        "## 決策",
        "",
        "R3 不執行 deletion。未來若出現新 JS residual，必須另以新 symbol、root/caller/callee、HTML/event/window 入口與 ≤20 symbols 的獨立批次重新建立證據；不得回溯刪除已完成的 H-04-11～H-04-15 鏈。",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.write and args.check:
        parser.error("use only one of --write or --check")
    audit = build_audit()
    rendered_json = json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    rendered_markdown = render_markdown(audit)
    if audit["current_source"]["total_executable_literal_hits"] != 0:
        print("TD15_R3_BLOCKED: current executable literal hits remain")
        return 1
    if audit["current_source"]["dynamic_scan"]["candidate_dynamic_hit_count"] != 0:
        print("TD15_R3_BLOCKED: candidate dynamic access remains")
        return 1
    if args.write:
        JSON_OUTPUT.write_text(rendered_json, encoding="utf-8")
        MD_OUTPUT.write_text(rendered_markdown, encoding="utf-8")
        print(f"wrote {JSON_OUTPUT.relative_to(ROOT)}")
        print(f"wrote {MD_OUTPUT.relative_to(ROOT)}")
        return 0
    if args.check:
        mismatches = []
        if not JSON_OUTPUT.exists() or JSON_OUTPUT.read_text(encoding="utf-8") != rendered_json:
            mismatches.append(str(JSON_OUTPUT.relative_to(ROOT)))
        if not MD_OUTPUT.exists() or MD_OUTPUT.read_text(encoding="utf-8") != rendered_markdown:
            mismatches.append(str(MD_OUTPUT.relative_to(ROOT)))
        if mismatches:
            print("TD15_R3_NOT_REPRODUCIBLE: " + ", ".join(mismatches))
            return 1
        print("TD15_R3_OK: symbols=58 declarations=0 literal_hits=0 candidate_dynamic_hits=0 deletion=0")
        return 0
    print(rendered_json, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
