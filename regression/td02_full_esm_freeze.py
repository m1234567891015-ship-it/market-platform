"""Freeze the pre-migration TD-02 full-site ESM state and propose waves.

This is an evidence-only gate.  It records the current 21-page script wiring,
the 895-symbol dependency inventory, asset fingerprints, and a conservative
wave grouping.  It does not modify HTML, JavaScript, production assets, or
baselines.
"""

from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_DATE = "2026-09-01"
MATRIX_JSON = ROOT / "docs" / "TD02-01_dependency_matrix_2026-08-31.json"
OUTPUT_JSON = ROOT / "docs" / "TD02_REMAIN_full_esm_freeze_2026-09-01.json"
OUTPUT_MD = ROOT / "docs" / "TD02_REMAIN_full_esm_freeze_2026-09-01.md"
EXPECTED_PAGES = 21
EXPECTED_SYMBOLS = 895
SCRIPT_RE = re.compile(r"<script\b[^>]*\bsrc=[\"']([^\"']+)[\"'][^>]*>", re.IGNORECASE)
PAGE_RE = re.compile(r"<body\b[^>]*\bdata-page=[\"']([^\"']+)[\"']", re.IGNORECASE)


class FreezeFailure(AssertionError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise FreezeFailure(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_utf8(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def page_records() -> list[dict]:
    records = []
    for path in sorted(ROOT.glob("*.html")):
        text = read_utf8(path)
        page_match = PAGE_RE.search(text)
        require(page_match is not None, f"missing data-page: {path.name}")
        scripts = [src.split("?", 1)[0] for src in SCRIPT_RE.findall(text)]
        records.append({
            "file": path.name,
            "data_page": page_match.group(1),
            "script_order": scripts,
            "html_sha256": sha256(path),
        })
    require(len(records) == EXPECTED_PAGES, f"expected {EXPECTED_PAGES} HTML pages, found {len(records)}")
    return records


def wave_for_page(record: dict) -> str:
    page = record["data_page"]
    if page == "derivatives-status":
        return "W01-completed-status-island"
    if page in {"asset-hub"}:
        return "W02-asset-hub"
    if page in {"global-market", "derivatives", "derivatives-ai", "derivatives-analytics", "derivatives-assets"}:
        return "W03-global-market-and-derivatives"
    if page in {"market", "tw", "tw-stocks", "tw-stock-search", "tw-etf", "tw-watchlist"}:
        return "W04-tw-market"
    if page in {"us", "us-stocks", "us-stock-search", "us-etf", "us-watchlist", "us-market-overview"}:
        return "W05-us-market"
    return "W06-unclassified-followup"


def build_freeze() -> dict:
    matrix = json.loads(MATRIX_JSON.read_text(encoding="utf-8-sig"))
    pages = page_records()
    symbols = matrix.get("symbols", [])
    require(len(symbols) == EXPECTED_SYMBOLS, f"expected {EXPECTED_SYMBOLS} symbols, found {len(symbols)}")
    require(matrix.get("scope", {}).get("classic_fallback_preserved") is True, "classic fallback is not preserved in matrix")
    require(matrix.get("scope", {}).get("html_switch") is False, "dependency matrix already records an HTML switch")

    assets = {}
    for relative in ["common-runtime.min.js", "route-bundle.min.js", "derivatives-status-esm-loader.js", "derivatives-status-esm.js", "derivatives-status-addon.min.js"]:
        path = ROOT / relative
        require(path.is_file(), f"missing current asset: {relative}")
        assets[relative] = {"bytes": path.stat().st_size, "sha256": sha256(path)}

    waves: dict[str, list[str]] = {}
    for record in pages:
        wave = wave_for_page(record)
        waves.setdefault(wave, []).append(record["file"])
        record["wave"] = wave
    require(set(waves["W01-completed-status-island"]) == {"derivatives-status.html"}, "status island wave mismatch")
    require(all("common-runtime.min.js" in record["script_order"] for record in pages), "not all pages use current runtime bundle")

    return {
        "schema_version": 1,
        "batch": "TD02-FULL-ESM-FREEZE",
        "snapshot_date": SNAPSHOT_DATE,
        "status": "TD02_FULL_ESM_PHASE_1_FROZEN_ARCHIVED",
        "scope": {
            "frontend_pages": EXPECTED_PAGES,
            "global_symbols": EXPECTED_SYMBOLS,
            "current_esm_pages": 1,
            "current_classic_pages": EXPECTED_PAGES - 1,
            "wave_count": len(waves),
        },
        "policy": {
            "production_wiring_changed": False,
            "baseline_changed": False,
            "classic_fallback_preserved": True,
            "runtime_data_modified": False,
            "browser_shadow_gate": "blocked-no-browser-backend",
        },
        "current_assets": assets,
        "dependency_matrix": {
            "source": "docs/TD02-01_dependency_matrix_2026-08-31.json",
            "symbol_count": len(symbols),
            "page_count": len(matrix.get("pages", [])),
            "dependency_edge_count": len(matrix.get("dependency_edges", [])),
            "cycles_requiring_bridge": matrix.get("cycles_requiring_bridge_or_deferred_import", []),
        },
        "waves": [{"wave": wave, "pages": sorted(files), "status": "completed" if wave.startswith("W01") else "pending-browser-shadow-gate"} for wave, files in sorted(waves.items())],
        "pages": pages,
        "next_gate": {
            "required_before_production_switch": [
                "browser-backed shadow test for every wave",
                "explicit bridge contract and duplicate-run guard",
                "normal ESM and classic rollback canary per wave",
                "21/21 page wiring, 895/895 symbols, 94/94 interactions, security, E2E and full verify",
            ],
            "production_switch_authorized_by_this_manifest": False,
        },
    }


def markdown_report(freeze: dict) -> str:
    lines = [
        "# TD-02 全站 ESM 遷移前凍結與分波（2026-09-01；暫時封存）",
        "",
        "本文件是 TD-02 全站 ESM 遷移的 Phase 1 freeze evidence。它只記錄目前 production wiring、895 symbols、21 頁與資產 fingerprint，不修改 HTML／JS／baseline。",
        "",
        "## 結論",
        "",
        f"- 狀態：`{freeze['status']}`。目前 ESM 頁面 {freeze['scope']['current_esm_pages']} 頁，classic 頁面 {freeze['scope']['current_classic_pages']} 頁。",
        "- TD02-REMAIN-01～03 的 `derivatives-status.html` island 作為 W01 已完成；其餘 wave 尚未通過 browser-backed shadow gate。",
        "- 本 freeze 不授權全站 production ESM switch；classic fallback、原 script order 與 rollback path 保留。",
        "",
        "## Waves",
        "",
        "| wave | pages | status |",
        "|---|---|---|",
    ]
    for wave in freeze["waves"]:
        lines.append(f"| `{wave['wave']}` | {', '.join(wave['pages'])} | `{wave['status']}` |")
    lines.extend([
        "",
        "## Required gate",
        "",
        "全站切換前必須完成每一 wave 的 browser-backed shadow、explicit bridge、正常／rollback canary，並通過 21/21 page wiring、895/895 symbols、94/94 interactions、API、DOM／pixel、security／CSP、E2E 與 full verify。",
        "",
        "目前工作階段沒有可用 browser backend；依最新決定，TD-02 全站 ESM 後續暫時封存。本文件只完成 freeze／分波，不得據此宣稱 Phase 2～4 或全站 ESM 已完成。",
        "",
        "完整 machine-readable freeze：`docs/TD02_REMAIN_full_esm_freeze_2026-09-01.json`。",
    ])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write freeze JSON and Markdown")
    parser.add_argument("--check", action="store_true", help="rebuild and validate freeze evidence")
    args = parser.parse_args()
    try:
        date.fromisoformat(SNAPSHOT_DATE)
        freeze = build_freeze()
        if args.write:
            OUTPUT_JSON.write_text(json.dumps(freeze, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="")
            OUTPUT_MD.write_text(markdown_report(freeze), encoding="utf-8", newline="")
        print(
            "TD02_FULL_ESM_FREEZE_OK: "
            f"pages={freeze['scope']['frontend_pages']} "
            f"symbols={freeze['scope']['global_symbols']} "
            f"esm_pages={freeze['scope']['current_esm_pages']} "
            f"classic_pages={freeze['scope']['current_classic_pages']} "
            f"waves={freeze['scope']['wave_count']} "
            "production_switch=false"
        )
        return 0
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError, FreezeFailure) as exc:
        print(f"TD02_FULL_ESM_FREEZE_FAIL: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
