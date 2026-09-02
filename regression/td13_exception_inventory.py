"""TD-13: inventory broad exception handlers in production Python modules.

This is an offline, read-only audit.  It distinguishes direct logging from
route-level delegation to ``api_exception_response`` and intentional backend
error translation, so a bare ``except Exception`` is not automatically treated
as a missing log.
"""
from __future__ import annotations

import ast
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRODUCTION_FILES = (
    "app.py",
    "builders.py",
    "cache.py",
    "derivatives_store.py",
    "fetch_registry.py",
    "fetchers.py",
    "market_config.py",
    "parsers.py",
    "routes_derivatives.py",
    "routes_global_market.py",
    "routes_system.py",
    "routes_twse.py",
    "security.py",
    "shared_state.py",
)


def _contains_call(node: ast.AST, names: set[str]) -> bool:
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        function = child.func
        if isinstance(function, ast.Name) and function.id in names:
            return True
        if isinstance(function, ast.Attribute) and function.attr in names:
            return True
    return False


def classify(handler: ast.ExceptHandler) -> str:
    if _contains_call(handler, {"debug", "info", "warning", "error", "exception"}):
        return "direct-log"
    if _contains_call(handler, {"api_exception_response"}):
        return "delegated-api-error-log"
    if any(isinstance(node, ast.Raise) for node in handler.body):
        return "translate-or-reraise"
    if any(isinstance(node, (ast.Pass, ast.Continue, ast.Break)) for node in handler.body):
        return "intentional-control-flow"
    return "fallback-without-direct-log"


def inventory() -> dict:
    rows = []
    for relative in PRODUCTION_FILES:
        path = ROOT / relative
        if not path.is_file():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=relative)
        for handler in ast.walk(tree):
            if not isinstance(handler, ast.ExceptHandler):
                continue
            if not isinstance(handler.type, ast.Name) or handler.type.id != "Exception":
                continue
            rows.append({
                "file": relative,
                "line": handler.lineno,
                "classification": classify(handler),
            })
    counts = Counter(row["classification"] for row in rows)
    return {
        "status": "TD13_EXCEPTION_INVENTORY_OK",
        "production_files": list(PRODUCTION_FILES),
        "broad_exception_count": len(rows),
        "classification_counts": dict(sorted(counts.items())),
        "rows": rows,
    }


if __name__ == "__main__":
    print(json.dumps(inventory(), ensure_ascii=False, indent=2, sort_keys=True))
