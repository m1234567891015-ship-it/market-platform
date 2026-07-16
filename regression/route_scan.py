"""掃描 app.py 原始碼中的 @app.route(...) 裝飾器,列出完整端點清單。

刻意用正規表達式掃描原始碼而非 import app 模組,
避免掃描階段就觸發背景執行緒或任何 side effect。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
APP_PY = REPO_ROOT / "app.py"

ROUTE_DECORATOR_RE = re.compile(
    r'@app\.route\(\s*"(?P<path>[^"]+)"\s*(?:,\s*methods\s*=\s*\[(?P<methods>[^\]]*)\])?\s*\)',
)


@dataclass
class Route:
    path: str
    methods: list[str] = field(default_factory=lambda: ["GET"])

    @property
    def is_get(self) -> bool:
        return "GET" in self.methods

    @property
    def is_api(self) -> bool:
        return self.path.startswith("/api/")

    @property
    def has_path_params(self) -> bool:
        return "<" in self.path


def scan_routes() -> list[Route]:
    text = APP_PY.read_text(encoding="utf-8")
    routes: list[Route] = []
    for match in ROUTE_DECORATOR_RE.finditer(text):
        path = match.group("path")
        methods_raw = match.group("methods")
        if methods_raw:
            methods = [m.strip().strip("'\"") for m in methods_raw.split(",") if m.strip()]
        else:
            methods = ["GET"]
        routes.append(Route(path=path, methods=methods))
    return routes


def api_get_routes() -> list[Route]:
    return [r for r in scan_routes() if r.is_api and r.is_get]


if __name__ == "__main__":
    all_routes = scan_routes()
    print(f"total routes: {len(all_routes)}")
    api_routes = [r for r in all_routes if r.is_api]
    print(f"api routes: {len(api_routes)}")
    api_get = api_get_routes()
    print(f"api GET routes: {len(api_get)}")
    for r in all_routes:
        print(f"  {r.methods!r:20} {r.path}")
