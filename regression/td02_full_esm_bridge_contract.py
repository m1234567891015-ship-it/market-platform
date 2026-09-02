"""Lock the TD-02 full-site ESM transitional bridge contract.

This batch turns the TD02-01 inventory and TD02-02 design into a checked,
machine-readable allowlist.  It deliberately does not publish globals, alter
HTML, or switch production entries; those are runtime/browser-gated actions.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / "docs" / "TD02-01_dependency_matrix_2026-08-31.json"
FREEZE_PATH = ROOT / "docs" / "TD02_REMAIN_full_esm_freeze_2026-09-01.json"
BASELINE_PATH = ROOT / "regression" / "baseline" / "frontend" / "global_symbols.json"
OUTPUT_JSON = ROOT / "docs" / "TD02_REMAIN_full_esm_bridge_contract_2026-09-01.json"
OUTPUT_MD = ROOT / "docs" / "TD02_REMAIN_full_esm_bridge_contract_2026-09-01.md"

WINDOW_PROPERTIES = {
    "TWSE_DATA": {
        "owner_source": "external/server-seeded window property",
        "consumer": "js/state.js",
        "reason": "state.js reads an optional preloaded seed before live fetch",
    },
    "TWSE_ALL_STOCKS": {
        "owner_source": "external/server-seeded window property",
        "consumer": "js/state.js",
        "reason": "state.js reads an optional preloaded seed before live fetch",
    },
    "__MARKET_PULSE_SAFE_INNER_HTML__": {
        "owner_source": "js/core.js",
        "consumer": "js/core.js",
        "reason": "private idempotence sentinel for the innerHTML safety guard",
    },
    "currentGlobalMarketPayload": {
        "owner_source": "js/page-us.js + js/page-global-market-options.js",
        "consumer": "js/page-us.js + js/page-global-market-options.js",
        "reason": "cross-route window payload handoff; replace with explicit context API",
    },
}


class ContractFailure(AssertionError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractFailure(message)


def read_json(path: Path) -> dict | list:
    require(path.is_file(), f"missing required artifact: {path.relative_to(ROOT)}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def symbol_index(matrix: dict) -> dict[str, dict]:
    rows = matrix.get("symbols", [])
    require(len(rows) == 895, f"expected 895 symbol rows, found {len(rows)}")
    index: dict[str, dict] = {}
    for row in rows:
        symbol = row.get("symbol")
        require(isinstance(symbol, str) and symbol, "symbol row has no name")
        require(symbol not in index, f"duplicate symbol owner: {symbol}")
        index[symbol] = row
    return index


def bridge_class(symbol: str, owner_candidate: str) -> str:
    if owner_candidate == "runtime/state" and not symbol.isupper():
        return "mutable-state"
    return "named-symbol"


def build_contract(matrix: dict, freeze: dict, baseline: list) -> dict:
    owners = symbol_index(matrix)
    require(len(baseline) == 895, f"expected 895 baseline symbols, found {len(baseline)}")
    require(set(baseline) == set(owners), "matrix/baseline symbol set drifted")
    require(freeze.get("status") == "TD02_FULL_ESM_PHASE_1_FROZEN_ARCHIVED", "freeze artifact is not the expected archived phase-1 lock")
    require(freeze.get("policy", {}).get("production_wiring_changed") is False, "freeze already has production wiring changes")
    require(freeze.get("policy", {}).get("classic_fallback_preserved") is True, "classic fallback is not preserved")

    entries: list[dict] = []
    for module in matrix.get("modules", []):
        consumer = module.get("source")
        consumer_module = module.get("candidate_module")
        for edge in module.get("required_global_bridge", []):
            symbol = edge.get("symbol")
            require(symbol in owners, f"bridge symbol is missing from owner inventory: {symbol}")
            owner = owners[symbol]
            require(owner.get("source") == edge.get("owner_source"), f"bridge owner drifted: {symbol}")
            require(owner.get("candidate_module") == edge.get("owner_candidate_module"), f"bridge module drifted: {symbol}")
            entries.append(
                {
                    "bridge_class": bridge_class(symbol, owner["candidate_module"]),
                    "consumer": consumer,
                    "consumer_module": consumer_module,
                    "symbol": symbol,
                    "owner_source": owner["source"],
                    "owner_candidate_module": owner["candidate_module"],
                    "removal_gate": "consumer uses named import or explicit store API and shadow verifier is green",
                }
            )

    for module in matrix.get("modules", []):
        for immediate in module.get("top_level_immediate_references", []):
            for symbol in immediate.get("symbols", []):
                require(symbol in owners, f"top-level entrypoint symbol is missing from owner inventory: {symbol}")
                owner = owners[symbol]
                entries.append(
                    {
                        "bridge_class": "entrypoint",
                        "consumer": module["source"],
                        "consumer_module": module["candidate_module"],
                        "symbol": symbol,
                        "owner_source": owner["source"],
                        "owner_candidate_module": owner["candidate_module"],
                        "removal_gate": "single ESM entry imports route facade before bootstrap evaluation and canary is green",
                    }
                )

    for symbol, details in WINDOW_PROPERTIES.items():
        entries.append(
            {
                "bridge_class": "window-property",
                "consumer": details["consumer"],
                "consumer_module": "compat/legacy-global-bridge",
                "symbol": symbol,
                "owner_source": details["owner_source"],
                "owner_candidate_module": "compat/legacy-global-bridge",
                "removal_gate": "all readers and writers use explicit input, store, or private safety adapter",
                "reason": details["reason"],
            }
        )

    contract = {
        "schema_version": 1,
        "batch": "TD02-FULL-ESM-BRIDGE-CONTRACT",
        "snapshot_date": "2026-09-01",
        "status": "TD02_FULL_ESM_PHASE_2_CONTRACT_LOCKED_ARCHIVED_NO_PRODUCTION_SWITCH",
        "scope": {
            "inventory_symbols": len(owners),
            "bridge_entries": len(entries),
            "required_global_bridge_entries": sum(len(module.get("required_global_bridge", [])) for module in matrix.get("modules", [])),
            "entrypoint_entries": sum(len(ref.get("symbols", [])) for module in matrix.get("modules", []) for ref in module.get("top_level_immediate_references", [])),
            "window_property_entries": len(WINDOW_PROPERTIES),
            "cycles_requiring_bridge_or_deferred_import": len(matrix.get("cycles_requiring_bridge_or_deferred_import", [])),
        },
        "policy": {
            "production_wiring_changed": False,
            "html_changed": False,
            "baseline_changed": False,
            "globals_published_by_this_batch": False,
            "classic_fallback_preserved": True,
            "browser_runtime_gate": "blocked-no-browser-backend",
        },
        "owner_rule": "each inventory symbol has exactly one source owner; bridge entries are aliases/adapters only",
        "entries": sorted(entries, key=lambda item: (item["consumer"], item["symbol"], item["bridge_class"])),
        "cycles": matrix.get("cycles_requiring_bridge_or_deferred_import", []),
        "dynamic_window_properties": matrix.get("dynamic_window_bridges", []),
        "rollback": "disable future ESM entry/bridge, restore H-10 production bundle, then classic lockfile order; status page may restore derivatives-ui addon",
        "next_gate": [
            "browser-backed shadow for each wave",
            "runtime owner-publish and duplicate-run canary",
            "normal ESM/classic rollback canary",
            "21/21 page wiring, 895/895 symbols, 94/94 interactions, security, E2E and full verify",
        ],
    }
    validate_contract(contract, matrix, baseline)
    return contract


def validate_contract(contract: dict, matrix: dict, baseline: list) -> None:
    require(contract.get("scope", {}).get("inventory_symbols") == 895, "contract inventory count drifted")
    require(contract.get("policy", {}).get("production_wiring_changed") is False, "contract must not authorize production wiring")
    require(contract.get("policy", {}).get("html_changed") is False, "bridge contract changed HTML")
    require(contract.get("policy", {}).get("baseline_changed") is False, "bridge contract changed baseline")
    require(contract.get("policy", {}).get("globals_published_by_this_batch") is False, "contract batch must not publish globals")
    entries = contract.get("entries", [])
    keys = [(row.get("consumer"), row.get("symbol"), row.get("bridge_class")) for row in entries]
    require(len(keys) == len(set(keys)), "duplicate bridge entry detected")
    owners = symbol_index(matrix)
    for row in entries:
        symbol = row.get("symbol")
        require(isinstance(symbol, str) and symbol, "bridge entry has no symbol")
        if row.get("bridge_class") == "window-property":
            details = WINDOW_PROPERTIES.get(symbol)
            require(details is not None, f"unregistered window property: {symbol}")
            require(row.get("owner_source") == details["owner_source"], f"window property owner drifted: {symbol}")
            require(row.get("owner_candidate_module") == "compat/legacy-global-bridge", f"window property module drifted: {symbol}")
        else:
            owner = owners.get(symbol)
            require(owner is not None, f"bridge symbol is missing from owner inventory: {symbol}")
            require(row.get("owner_source") == owner["source"], f"bridge owner drifted: {symbol}")
            require(row.get("owner_candidate_module") == owner["candidate_module"], f"bridge module drifted: {symbol}")
    expected_required = {
        (module["source"], edge["symbol"])
        for module in matrix.get("modules", [])
        for edge in module.get("required_global_bridge", [])
    }
    actual_required = {
        (row["consumer"], row["symbol"])
        for row in entries
        if row["bridge_class"] in {"named-symbol", "mutable-state"}
    }
    require(expected_required <= actual_required, "required global bridge entry is missing")
    expected_entrypoints = {
        (module["source"], symbol)
        for module in matrix.get("modules", [])
        for immediate in module.get("top_level_immediate_references", [])
        for symbol in immediate.get("symbols", [])
    }
    actual_entrypoints = {
        (row["consumer"], row["symbol"])
        for row in entries
        if row["bridge_class"] == "entrypoint"
    }
    require(expected_entrypoints <= actual_entrypoints, "top-level entrypoint bridge is missing")
    actual_windows = {row.get("symbol") for row in entries if row.get("bridge_class") == "window-property"}
    require(actual_windows == set(WINDOW_PROPERTIES), "dynamic window property allowlist drifted")
    require(len(baseline) == 895 and len(matrix.get("symbols", [])) == 895, "owner inventory is incomplete")
    require(len(matrix.get("cycles_requiring_bridge_or_deferred_import", [])) == 2, "controlled cycle inventory drifted")


def error_injection(contract: dict, matrix: dict, baseline: list) -> dict:
    injected = copy.deepcopy(contract)
    injected["entries"][0]["owner_source"] = "js/unregistered-owner.js"
    try:
        validate_contract(injected, matrix, baseline)
    except ContractFailure:
        return {"duplicate_or_owner_mutation": "caught"}
    raise ContractFailure("error injection was not caught: owner mutation")


def render_markdown(contract: dict) -> str:
    counts = contract["scope"]
    lines = [
        "# TD-02 全站 ESM bridge contract lock（2026-09-01；暫時封存）",
        "",
        "本批將 TD02-01 的 895-symbol owner inventory 與 TD02-02 的 transitional bridge 設計落成 machine-readable allowlist。它不發布 global、不改 HTML、不切 production entry；正式 runtime wiring 仍須通過 browser-backed shadow／canary。",
        "",
        "## 結論",
        "",
        f"- 狀態：`{contract['status']}`。共鎖定 {counts['bridge_entries']} 個 contract entries：required global bridge {counts['required_global_bridge_entries']}、entrypoint {counts['entrypoint_entries']}、window property {counts['window_property_entries']}。",
        "- 每個 symbol 維持單一 source owner；`escapeHtml` 仍由 `js/core.js` 擁有，bridge 只能是 alias／adapter，不複製 function body。",
        "- `runtime/bootstrap ↔ route/page-tw` 與 global-market cluster 兩組循環維持受控清單；未通過 deferred entry／cluster facade 的 browser proof 前不可切波。",
        "- 本批 production wiring、HTML、baseline、classic fallback 均未變更；目前 browser backend 不可用，且依最新決定 Phase 3 接線與 Phase 4 收斂 gate 暫時封存。",
        "",
        "## Bridge classes",
        "",
        "| class | 內容 | 移除條件 |",
        "|---|---|---|",
        "| `named-symbol` | TD02-01 required global bridge allowlist | consumer 改成 named import 且 shadow verifier 綠燈 |",
        "| `mutable-state` | state owner 的 getter／setter 過渡 adapter | 所有 reader／writer 改走 explicit store API 且 interaction 綠燈 |",
        "| `entrypoint` | bootstrap 的 top-level route binding | 單一 ESM entry 完成 route import 且 canary 綠燈 |",
        "| `window-property` | TWSE seed、payload handoff、innerHTML safety sentinel | 改成 explicit input／store／private safety adapter |",
        "",
        "## Gate 與 rollback",
        "",
        "正式接線前仍需每一 wave 的 browser-backed shadow、owner-publish／duplicate-run canary、正常／classic rollback canary，以及 21/21 page wiring、895/895 symbols、94/94 interactions、security、E2E 與 full verify。失敗時固定回退：ESM entry／bridge off → H-10 bundle → classic lockfile order；derivatives-status 另可回 classic addon。",
        "",
        "完整 allowlist：`docs/TD02_REMAIN_full_esm_bridge_contract_2026-09-01.json`。",
    ]
    return "\n".join(lines) + "\n"


def run(write: bool) -> dict:
    matrix = read_json(MATRIX_PATH)
    freeze = read_json(FREEZE_PATH)
    baseline = read_json(BASELINE_PATH)
    require(isinstance(matrix, dict) and isinstance(freeze, dict) and isinstance(baseline, list), "invalid TD02 bridge inputs")
    contract = build_contract(matrix, freeze, baseline)
    contract["error_injection"] = error_injection(contract, matrix, baseline)
    if write:
        OUTPUT_JSON.write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="")
        OUTPUT_MD.write_text(render_markdown(contract), encoding="utf-8", newline="")
    return contract


def main() -> int:
    write = "--write" in sys.argv[1:]
    try:
        contract = run(write)
    except (OSError, ContractFailure, json.JSONDecodeError) as exc:
        print(f"TD02_FULL_ESM_BRIDGE_FAIL: {exc}", file=sys.stderr)
        return 1
    print(
        "TD02_FULL_ESM_BRIDGE_OK: "
        f"entries={contract['scope']['bridge_entries']} "
        f"required={contract['scope']['required_global_bridge_entries']} "
        f"entrypoints={contract['scope']['entrypoint_entries']} "
        f"windows={contract['scope']['window_property_entries']} "
        "production_switch=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
