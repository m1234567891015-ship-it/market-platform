"""TD02-01: reproducible classic-slice to candidate-module inventory.

This is an offline design-time inventory.  It reads the locked TD-18 source
order, the current HTML entries, and the frozen global-symbol baseline; it
does not edit HTML, JavaScript, CSP, baselines, or runtime data.

The scanner is intentionally conservative.  It records source-level
cross-slice references and top-level immediate references, then leaves the
final ESM import/bridge naming decision to TD02-02.  The generated JSON is the
machine-readable evidence; the Markdown file is a review-friendly summary.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
REGRESSION = ROOT / "regression"
LOCKFILE = REGRESSION / "td18_shadow_build.lock.json"
BASELINE = REGRESSION / "baseline" / "frontend" / "global_symbols.json"
JSON_OUTPUT = ROOT / "docs" / "TD02-01_dependency_matrix_2026-08-31.json"
MARKDOWN_OUTPUT = ROOT / "docs" / "TD02-01_dependency_matrix_2026-08-31.md"
SNAPSHOT_DATE = "2026-08-31"

sys.path.insert(0, str(ROOT))
from security_guardrail_check import (  # noqa: E402
    IDENTIFIER_RE,
    JS_RESERVED_WORDS,
    TOP_LEVEL_FUNCTION_RE,
    TOP_LEVEL_VAR_RE,
    find_matching_close,
    js_top_level_declared_names,
    js_top_level_immediate_statement_identifiers,
    locally_bound_names,
    strip_js_noise,
)


SOURCE_CANDIDATES = {
    "pwa.js": ("runtime/pwa", "isolated-runtime"),
    "js/state.js": ("runtime/state", "shared-runtime"),
    "js/core.js": ("runtime/core", "shared-runtime"),
    "js/api.js": ("runtime/api", "shared-runtime"),
    "js/shared-calc.js": ("runtime/shared-calc", "shared-runtime"),
    "js/render-shared.js": ("runtime/render-shared", "shared-runtime"),
    "js/charts.js": ("runtime/charts", "shared-runtime"),
    "js/stock-detail.js": ("route/stock-detail", "route-support"),
    "js/page-home.js": ("route/page-home", "route-specific"),
    "js/page-us.js": ("route/page-us", "route-specific"),
    "js/page-global-market-futures.js": ("route/global-market-futures", "route-specific"),
    "js/page-global-market-options.js": ("route/global-market-options", "route-specific"),
    "js/page-global-market-assethub.js": ("route/global-market-assethub", "route-specific"),
    "js/page-tw.js": ("route/page-tw", "route-specific"),
    "js/legacy-unclassified.js": ("route/legacy-unclassified", "legacy-compat"),
    "js/main.js": ("runtime/bootstrap", "bootstrap"),
    "app.js": ("compat/app-shell", "compatibility-shell"),
    "derivatives-ui.js": ("route/derivatives-status-addon", "route-specific-addon"),
}


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.body_attrs: dict[str, str] = {}
        self.scripts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.lower(): value or "" for key, value in attrs}
        if tag.lower() == "body":
            self.body_attrs = values
        if tag.lower() == "script" and values.get("src"):
            source = values["src"].split("?", 1)[0]
            # The dependency matrix models the logical production boundary;
            # minified and unminified artifacts share the same locked inputs.
            self.scripts.append(source.replace(".min.js", ".js"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8"))


def locked_inputs() -> tuple[list[str], dict[str, str], dict[str, list[str]]]:
    lock = load_json(LOCKFILE)
    assert isinstance(lock, dict)
    bundle_by_input: dict[str, str] = {}
    bundle_inputs: dict[str, list[str]] = {}
    ordered: list[str] = []
    for bundle in lock["bundles"]:
        bundle_inputs[bundle["name"]] = list(bundle["inputs"])
        for relative in bundle["inputs"]:
            bundle_by_input[relative] = bundle["name"]
            ordered.append(relative)
    return ordered, bundle_by_input, bundle_inputs


def read_pages() -> list[dict]:
    pages = []
    for html_file in sorted(ROOT.glob("*.html")):
        parser = PageParser()
        parser.feed(html_file.read_text(encoding="utf-8-sig"))
        pages.append(
            {
                "file": html_file.name,
                "data_page": parser.body_attrs.get("data-page", ""),
                "market_category": parser.body_attrs.get("data-market-category", ""),
                "production_script_order": [
                    source for source in parser.scripts if source in {"common-runtime.js", "route-bundle.js", "derivatives-status-addon.js"}
                ],
            }
        )
    if len(pages) != 21:
        raise ValueError(f"expected 21 HTML pages, found {len(pages)}")
    return pages


def route_owner(page: dict) -> str:
    data_page = page["data_page"]
    category = page["market_category"]
    if data_page in {"home", "market"}:
        return "js/page-home.js"
    if data_page in {"sectors", "watchlist", "search", "tw-etf"}:
        return "js/page-tw.js"
    if data_page == "global-market":
        if category == "options":
            return "js/page-global-market-options.js"
        return "js/page-global-market-futures.js"
    if data_page in {"asset-hub", "derivatives-analytics", "derivatives-ai"}:
        return "js/page-global-market-assethub.js"
    if data_page in {"us-etf", "us-stock-search", "us-watchlist"}:
        return "js/page-us.js"
    if data_page == "derivatives-status":
        return "derivatives-ui.js"
    raise ValueError(f"unmapped data-page: {data_page!r}")


def top_level_function_spans(source: str) -> list[tuple[str, int, int, int, int, set[str]]]:
    """Return (name, start, end, body_start, body_end, parameters)."""
    stripped = strip_js_noise(source)
    result = []
    for match in TOP_LEVEL_FUNCTION_RE.finditer(stripped):
        name = match.group(1)
        paren_open = match.end() - 1
        paren_close = find_matching_close(stripped, paren_open)
        brace_open = stripped.find("{", paren_close)
        if brace_open < 0:
            continue
        brace_close = find_matching_close(stripped, brace_open)
        params = {
            item.group(0)
            for item in IDENTIFIER_RE.finditer(stripped[paren_open + 1 : paren_close])
        }
        result.append((name, match.start(), brace_close + 1, brace_open + 1, brace_close, params))
    return result


def declaration_rows(relative: str, source: str) -> list[dict]:
    stripped = strip_js_noise(source)
    function_names = {
        match.group(1): match.start() for match in TOP_LEVEL_FUNCTION_RE.finditer(stripped)
    }
    variable_names = {
        match.group(1): match.start() for match in TOP_LEVEL_VAR_RE.finditer(stripped)
    }
    rows = []
    for name in sorted(set(function_names) | set(variable_names)):
        pos = function_names.get(name, variable_names.get(name, 0))
        rows.append(
            {
                "symbol": name,
                "kind": "function" if name in function_names else "state-or-constant",
                "source": relative,
                "line": stripped.count("\n", 0, pos) + 1,
            }
        )
    return rows


def identifiers_for_function(stripped: str, span: tuple[str, int, int, int, int, set[str]]) -> set[str]:
    name, _start, _end, body_start, body_end, params = span
    body = stripped[body_start:body_end]
    identifiers = {match.group(0) for match in IDENTIFIER_RE.finditer(body)}
    identifiers -= JS_RESERVED_WORDS
    identifiers -= locally_bound_names(body)
    identifiers -= params
    identifiers.discard(name)
    return identifiers


def cross_slice_refs(
    source: str,
    owned: set[str],
    all_symbols: set[str],
) -> set[str]:
    """Collect global candidates while respecting top-level function locals."""
    stripped = strip_js_noise(source)
    refs: set[str] = set()
    spans = top_level_function_spans(source)
    for span in spans:
        refs |= identifiers_for_function(stripped, span) & all_symbols

    chars = list(stripped)
    for _name, start, end, _body_start, _body_end, _params in spans:
        for index in range(start, min(end, len(chars))):
            if chars[index] != "\n":
                chars[index] = " "
    top_level_text = "".join(chars)
    refs |= {
        match.group(0)
        for match in IDENTIFIER_RE.finditer(top_level_text)
    } & all_symbols
    refs -= owned
    return refs


def immediate_refs(source: str, owned: set[str], all_symbols: set[str]) -> list[dict]:
    result = []
    for line, identifiers in js_top_level_immediate_statement_identifiers(source):
        refs = sorted((identifiers & all_symbols) - owned)
        if refs:
            result.append({"line": line, "symbols": refs})
    return result


def dynamic_window_bridges(sources: dict[str, str]) -> list[dict]:
    interesting = {"TWSE_DATA", "TWSE_ALL_STOCKS", "currentGlobalMarketPayload", "__MARKET_PULSE_SAFE_INNER_HTML__"}
    occurrences: dict[str, dict[str, list[int]]] = defaultdict(lambda: {"read": [], "write": []})
    pattern = re.compile(r"window\.([A-Za-z_$][\w$]*)")
    for relative, source in sources.items():
        for match in pattern.finditer(source):
            name = match.group(1)
            if name not in interesting:
                continue
            line = source.count("\n", 0, match.start()) + 1
            tail = source[match.end() : match.end() + 40]
            bucket = "write" if re.match(r"\s*=", tail) else "read"
            occurrences[name][bucket].append(line)
    rows = []
    for name in sorted(occurrences):
        locations = occurrences[name]
        if name == "TWSE_DATA" or name == "TWSE_ALL_STOCKS":
            owner = "external/server-seeded window property"
            reason = "state.js reads an optional preloaded seed before live fetch; preserve as an explicit runtime input"
        elif name == "__MARKET_PULSE_SAFE_INNER_HTML__":
            owner = "js/core.js"
            reason = "idempotence sentinel for the innerHTML safety guard; keep private to the safety adapter"
        else:
            owner = "js/page-us.js + js/page-global-market-options.js"
            reason = "cross-route window payload handoff; replace with an explicit store/import before removing the bridge"
        rows.append(
            {
                "property": name,
                "owner": owner,
                "reason": reason,
                "read_lines": sorted(locations["read"]),
                "write_lines": sorted(locations["write"]),
            }
        )
    return rows


def strongly_connected_components(nodes: Iterable[str], edges: dict[str, set[str]]) -> list[list[str]]:
    index = 0
    stack: list[str] = []
    on_stack: set[str] = set()
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    components: list[list[str]] = []

    def visit(node: str) -> None:
        nonlocal index
        indices[node] = index
        lowlinks[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)
        for target in sorted(edges.get(node, set())):
            if target not in indices:
                visit(target)
                lowlinks[node] = min(lowlinks[node], lowlinks[target])
            elif target in on_stack:
                lowlinks[node] = min(lowlinks[node], indices[target])
        if lowlinks[node] != indices[node]:
            return
        component = []
        while True:
            target = stack.pop()
            on_stack.remove(target)
            component.append(target)
            if target == node:
                break
        components.append(sorted(component))

    for node in sorted(nodes):
        if node not in indices:
            visit(node)
    return sorted(components, key=lambda component: component[0])


def build_matrix() -> dict:
    ordered_inputs, bundle_by_input, bundle_inputs = locked_inputs()
    pages = read_pages()
    source_paths = [relative for relative in ordered_inputs if relative in SOURCE_CANDIDATES]
    sources = {
        relative: (ROOT / relative).read_text(encoding="utf-8-sig")
        for relative in source_paths
    }
    baseline = set(load_json(BASELINE))
    declarations = {
        relative: js_top_level_declared_names(source)
        for relative, source in sources.items()
        if relative.startswith("js/") or relative == "app.js"
    }
    symbol_owner: dict[str, str] = {}
    for relative, names in declarations.items():
        for name in names:
            if name in symbol_owner:
                raise ValueError(f"duplicate global symbol {name}: {symbol_owner[name]} and {relative}")
            symbol_owner[name] = relative
    if set(symbol_owner) != baseline:
        raise ValueError(
            f"global symbol baseline mismatch: baseline={len(baseline)}, current={len(symbol_owner)}, "
            f"missing={sorted(baseline - set(symbol_owner))[:10]}, extra={sorted(set(symbol_owner) - baseline)[:10]}"
        )

    all_symbols = set(symbol_owner)
    source_rows = []
    edge_symbols: dict[tuple[str, str], set[str]] = defaultdict(set)
    for relative in source_paths:
        candidate, kind = SOURCE_CANDIDATES[relative]
        owned = declarations.get(relative, set())
        refs = cross_slice_refs(sources[relative], owned, all_symbols)
        by_target: dict[str, list[str]] = defaultdict(list)
        for symbol in sorted(refs):
            by_target[symbol_owner[symbol]].append(symbol)
            edge_symbols[(relative, symbol_owner[symbol])].add(symbol)
        source_rows.append(
            {
                "source": relative,
                "candidate_module": candidate,
                "kind": kind,
                "bundle": bundle_by_input.get(relative, "not-in-td18-bundle"),
                "fallback_order": ordered_inputs.index(relative) + 1 if relative in ordered_inputs else None,
                "owned_symbol_count": len(owned),
                "owned_symbols": sorted(owned),
                "required_global_bridge": [
                    {
                        "symbol": symbol,
                        "owner_source": symbol_owner[symbol],
                        "owner_candidate_module": SOURCE_CANDIDATES[symbol_owner[symbol]][0],
                        "reason": "cross-slice read/call; replace with an explicit ESM import before bridge removal",
                    }
                    for symbol in sorted(refs)
                ],
                "dependency_targets": [
                    {
                        "source": target,
                        "candidate_module": SOURCE_CANDIDATES[target][0],
                        "symbols": names,
                    }
                    for target, names in sorted(by_target.items())
                ],
                "top_level_immediate_references": immediate_refs(sources[relative], owned, all_symbols),
                "pages": [page["file"] for page in pages if route_owner(page) == relative],
            }
        )

    edges = defaultdict(set)
    for (source, target) in edge_symbols:
        edges[source].add(target)
    sccs = strongly_connected_components(declarations, edges)
    cycles = [component for component in sccs if len(component) > 1]
    cycle_by_source = {source: cycle for cycle in cycles for source in cycle}

    symbol_rows = []
    for relative in sorted(declarations):
        for row in declaration_rows(relative, sources[relative]):
            row["candidate_module"] = SOURCE_CANDIDATES[relative][0]
            row["consumers"] = sorted(
                source for source, refs in ((item["source"], item["required_global_bridge"]) for item in source_rows)
                if any(entry["symbol"] == row["symbol"] for entry in refs)
            )
            symbol_rows.append(row)

    edges_rows = [
        {
            "from_source": source,
            "from_candidate_module": SOURCE_CANDIDATES[source][0],
            "to_source": target,
            "to_candidate_module": SOURCE_CANDIDATES[target][0],
            "symbols": sorted(symbols),
        }
        for (source, target), symbols in sorted(edge_symbols.items())
    ]

    production_orders = sorted({tuple(page["production_script_order"]) for page in pages})
    production_order_rows = [list(order) for order in production_orders]
    dynamic = dynamic_window_bridges(sources)

    route_pages = {
        "bootstrap": [page["file"] for page in pages],
        "runtime": [page["file"] for page in pages],
        "route_owner": {page["file"]: route_owner(page) for page in pages},
    }
    return {
        "schema_version": 1,
        "batch": "TD02-01",
        "snapshot_date": SNAPSHOT_DATE,
        "scope": {
            "purpose": "classic slice -> candidate ESM module -> required global bridge inventory",
            "behavior_change": False,
            "html_switch": False,
            "classic_fallback_preserved": True,
            "baseline_modified": False,
            "csp_modified": False,
            "runtime_data_modified": False,
        },
        "evidence": {
            "html_page_count": len(pages),
            "global_symbol_count": len(baseline),
            "global_symbol_baseline": str(BASELINE.relative_to(ROOT)).replace("\\", "/"),
            "global_symbol_baseline_sha256": sha256(BASELINE),
            "td18_lockfile": str(LOCKFILE.relative_to(ROOT)).replace("\\", "/"),
            "td18_input_order": ordered_inputs,
            "classic_fallback_order": [relative for relative in ordered_inputs if relative != "derivatives-ui.js"],
            "status_addon_order": [relative for relative in ordered_inputs if relative != "derivatives-ui.js"] + ["derivatives-ui.js"],
            "td18_bundle_inputs": bundle_inputs,
            "production_script_orders": production_order_rows,
            "source_hashes": {relative: sha256(ROOT / relative) for relative in source_paths},
        },
        "pages": pages,
        "modules": source_rows,
        "dependency_edges": edges_rows,
        "cycles_requiring_bridge_or_deferred_import": [
            {
                "sources": component,
                "candidate_modules": [SOURCE_CANDIDATES[source][0] for source in component],
                "reason": "mutual cross-slice references; do not perform direct ESM cutover until TD02-02 defines a deferred entrypoint or temporary bridge",
            }
            for component in cycles
        ],
        "top_level_initialization_gate": [
            {
                "source": row["source"],
                "candidate_module": row["candidate_module"],
                "references": row["top_level_immediate_references"],
                "status": "bridge-or-import-required" if row["top_level_immediate_references"] else "no-cross-slice-immediate-reference",
            }
            for row in source_rows
        ],
        "dynamic_window_bridges": dynamic,
        "symbols": symbol_rows,
        "rollback": {
            "production_entry": "restore each HTML script list to the classic input order in evidence.td18_input_order",
            "classic_order": [relative for relative in ordered_inputs if relative != "derivatives-ui.js"],
            "status_addon_order": [relative for relative in ordered_inputs if relative != "derivatives-ui.js"] + ["derivatives-ui.js"],
            "prohibited_in_this_batch": ["HTML rewiring", "classic slice removal", "CSP/cache/deployment changes", "baseline updates"],
        },
        "review_notes": {
            "scanner_limit": "Source-level references are deterministic lexical candidates with local function bindings removed; TD02-02 must review each bridge edge before naming imports or exports.",
            "current_production_boundary": "All ordinary pages execute common-runtime.js then route-bundle.js; derivatives-status.html appends derivatives-status-addon.js.",
            "legacy_unclassified": "js/legacy-unclassified.js remains an empty compatibility slot in the current source set; no symbol was deleted by TD02-01.",
            "app_shell": "app.js remains an empty compatibility shell and is still listed in the classic fallback order.",
        },
    }


def render_markdown(matrix: dict) -> str:
    evidence = matrix["evidence"]
    modules = matrix["modules"]
    lines = [
        "# TD02-01 前端依賴矩陣（2026-08-31）",
        "",
        "> 本文件是 TD02-01 的盤點產物；不切換 HTML、不移除 classic slices、不修改 baseline/CSP/部署。",
        "> 機器可重現來源為同名 `.json` 與 `regression/td02_01_dependency_matrix.py`。",
        "",
        "## 1. 盤點結論",
        "",
        f"- 21 頁目前 production script order 有 {len(evidence['production_script_orders'])} 種：`{' → '.join(evidence['production_script_orders'][0])}`；`derivatives-status.html` 另加 addon。",
        f"- classic fallback 輸入順序共 {len(evidence['td18_input_order'])} 個檔案，global symbol owner 共 {evidence['global_symbol_count']} 個，與 baseline SHA-256 `{evidence['global_symbol_baseline_sha256']}` 對齊。",
        f"- 目前偵測到 {len(matrix['dependency_edges'])} 條跨 slice dependency edges、{sum(len(edge['symbols']) for edge in matrix['dependency_edges'])} 個跨 slice symbol references。",
        f"- 需要 TD02-02 處理的互相依賴元件：{len(matrix['cycles_requiring_bridge_or_deferred_import'])} 組；TD02-01 不接線、不定義正式 bridge API。",
        "",
        "## 2. 現況載入與回退契約",
        "",
        "| 層 | 現況 | TD02-01 保留的契約 |",
        "|---|---|---|",
        "| Production | `common-runtime.js → route-bundle.js`；status 頁尾端再載入 addon | 不改 HTML 入口 |",
        f"| Classic fallback | `{' → '.join(evidence['classic_fallback_order'])}` | 仍可立即恢復，順序不可重排 |",
        "| Symbol scope | classic source slices 共享全域作用域 | 每個 symbol 一個 owner；bridge 移除前不得遺失 |",
        "| Safety | `escapeHtml`／innerHTML guard 位於 runtime/core | TD02-02 必須維持單一來源與執行時機 |",
        "",
        "## 3. Slice → candidate module → bridge",
        "",
        "`candidate_module` 是 TD02-02 的候選命名邊界，不代表本批已建立 ESM 檔案或 export/import。所有 bridge symbol 的完整 owner 與 consumer 在 JSON 的 `symbols`、`required_global_bridge` 可逐項核對。",
        "",
        "| classic source | candidate module | bundle | fallback order | owned globals | route pages | immediate cross-slice refs | dependency targets |",
        "|---|---|---|---:|---:|---|---|---|",
    ]
    for row in modules:
        targets = ", ".join(item["source"] for item in row["dependency_targets"]) or "—"
        immediate = ", ".join(
            symbol for item in row["top_level_immediate_references"] for symbol in item["symbols"]
        ) or "—"
        pages = ", ".join(row["pages"]) or "shared/all pages"
        lines.append(
            f"| `{row['source']}` | `{row['candidate_module']}` | `{row['bundle']}` | {row['fallback_order']} | {row['owned_symbol_count']} | {pages} | {immediate} | {targets} |"
        )

    lines += [
        "",
        "## 4. 跨 slice dependency edges",
        "",
        "以下每列的 symbol 都有唯一 owner；遷移過渡期先視為 required global bridge，TD02-02 再決定改成 named import、deferred entrypoint 或保留 bridge。",
        "",
        "| from | to / owner | symbols |",
        "|---|---|---|",
    ]
    for edge in matrix["dependency_edges"]:
        lines.append(
            f"| `{edge['from_source']}` | `{edge['to_source']}` (`{edge['to_candidate_module']}`) | {', '.join(f'`{name}`' for name in edge['symbols'])} |"
        )

    lines += ["", "## 5. 循環與頂層初始化", ""]
    if matrix["cycles_requiring_bridge_or_deferred_import"]:
        lines.append("循環依賴不可在 TD02-01 直接消除：")
        lines.append("")
        for cycle in matrix["cycles_requiring_bridge_or_deferred_import"]:
            lines.append(f"- `{ ' ↔ '.join(cycle['sources']) }`：{cycle['reason']}")
    else:
        lines.append("未發現跨 slice 循環依賴。")
    lines += ["", "頂層立即執行引用："]
    lines.append("")
    lines.append("| source | line | symbols | gate |")
    lines.append("|---|---:|---|---|")
    any_immediate = False
    for row in modules:
        for item in row["top_level_immediate_references"]:
            any_immediate = True
            lines.append(
                f"| `{row['source']}` | {item['line']} | {', '.join(f'`{name}`' for name in item['symbols'])} | ESM execution must import or bridge before evaluation |"
            )
    if not any_immediate:
        lines.append("| — | — | — | no cross-slice immediate references |")

    lines += ["", "## 6. Dynamic window bridge", "", "| property | owner | reads | writes | reason |", "|---|---|---|---|---|"]
    for row in matrix["dynamic_window_bridges"]:
        lines.append(
            f"| `{row['property']}` | {row['owner']} | {', '.join(map(str, row['read_lines'])) or '—'} | {', '.join(map(str, row['write_lines'])) or '—'} | {row['reason']} |"
        )

    lines += [
        "",
        "## 7. TD02-02 handoff rules",
        "",
        "1. 以 JSON 的 symbol owner 作唯一 owner；不得複製 `escapeHtml` 或其他 global definition。",
        "2. `required_global_bridge` 在 consumer 改成顯式 import、或由 deferred entrypoint 接手前必須保留；不得先刪 classic binding。",
        "3. `top_level_initialization_gate` 的引用在 ESM 執行前必須可取得；函式本體內的晚載入引用可延後到呼叫時，但必須在 TD02-02 逐項確認。",
        "4. 三個 global-market source 與 `main`／`page-tw` 的循環需採 deferred entrypoint 或暫時 bridge；不得以重排 HTML 掩蓋循環。",
        "5. `currentGlobalMarketPayload`、server-seeded `TWSE_DATA`／`TWSE_ALL_STOCKS` 與 innerHTML safety sentinel 是動態 window 契約，不能只靠靜態 export/import 推測。",
        "",
        "## 8. 回退與明確排除",
        "",
        f"回退方式：將 HTML script list 恢復為 lockfile 的 classic 順序：`{' → '.join(evidence['classic_fallback_order'])}`；`derivatives-status.html` 再接 `derivatives-ui.js`。本批沒有改動可回退的 production wiring。",
        "",
        "本批明確不做：ESM 接線、移除 classic slices、改變頁面行為、更新 global-symbol baseline、CSP、Service Worker、cache、部署設定、SQLite 或 `twse-cache.json`。",
        "",
        "## 9. 重現指令",
        "",
        "```text",
        "python regression/td02_01_dependency_matrix.py --write",
        "python regression/td02_01_dependency_matrix.py --check",
        "```",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="write the checked-in JSON and Markdown artifacts")
    parser.add_argument("--check", action="store_true", help="rebuild in memory and compare checked-in artifacts")
    args = parser.parse_args()
    if args.write and args.check:
        parser.error("use only one of --write or --check")
    matrix = build_matrix()
    rendered_json = json.dumps(matrix, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    rendered_markdown = render_markdown(matrix)
    if args.write:
        JSON_OUTPUT.write_text(rendered_json, encoding="utf-8")
        MARKDOWN_OUTPUT.write_text(rendered_markdown, encoding="utf-8")
        print(f"wrote {JSON_OUTPUT.relative_to(ROOT)}")
        print(f"wrote {MARKDOWN_OUTPUT.relative_to(ROOT)}")
        return 0
    if args.check:
        mismatches = []
        if not JSON_OUTPUT.exists() or JSON_OUTPUT.read_text(encoding="utf-8") != rendered_json:
            mismatches.append(str(JSON_OUTPUT.relative_to(ROOT)))
        if not MARKDOWN_OUTPUT.exists() or MARKDOWN_OUTPUT.read_text(encoding="utf-8") != rendered_markdown:
            mismatches.append(str(MARKDOWN_OUTPUT.relative_to(ROOT)))
        if mismatches:
            print("TD02_01_MATRIX_NOT_REPRODUCIBLE: " + ", ".join(mismatches))
            return 1
        print(f"TD02_01_MATRIX_OK: pages=21 symbols={len(matrix['symbols'])} edges={len(matrix['dependency_edges'])}")
        return 0
    print(rendered_json, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
