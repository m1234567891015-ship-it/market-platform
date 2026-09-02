"""Audit shared navigation and declared first-load static resources.

This is intentionally separate from the screenshot baseline: it measures the
HTML-declared JS/CSS payload without changing the baseline or treating dynamic
API responses as static assets.  The browser pass also verifies the runtime
single-source navigation and active state on every page.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REGRESSION_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(REGRESSION_DIR))

EXPECTED_NAV = [
    ("market-overview.html", "台股盤勢"),
    ("tw-stocks.html", "台股類股"),
    ("tw-etf.html", "台股 ETF"),
    ("tw-stock-search.html", "個股搜尋"),
    ("tw-Optional-stocks.html", "自選股"),
    ("us-market-overview.html", "美股盤勢"),
    ("us-stocks.html", "美股市場"),
    ("us-etf.html", "美股ETF"),
    ("us-stock-search.html", "美股搜尋"),
    ("us-watchlist.html", "美股自選"),
    ("international-finance.html", "貴金屬與債券"),
    ("bonds.html", "債券"),
    ("precious-metals.html", "貴金屬"),
    ("derivatives-assets.html", "期權"),
    ("futures.html", "期貨"),
    ("options.html", "選擇權"),
    ("derivatives-analytics.html", "期權分析"),
    ("derivatives-status.html", "系統維護"),
]


class ResourceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.references: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "script" and values.get("src"):
            self.references.append(values["src"] or "")
        elif tag == "link" and "stylesheet" in (values.get("rel") or "").split():
            if values.get("href"):
                self.references.append(values["href"] or "")


def _asset_path(reference: str) -> Path | None:
    clean = reference.split("?", 1)[0].split("#", 1)[0]
    if not clean or re.match(r"^[a-z][a-z0-9+.-]*://", clean, re.I):
        return None
    relative = clean.lstrip("/")
    candidate = (REPO_ROOT / relative).resolve()
    try:
        candidate.relative_to(REPO_ROOT.resolve())
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def declared_payload() -> dict[str, object]:
    pages: dict[str, dict[str, object]] = {}
    all_assets: dict[str, int] = {}
    for page in sorted(REPO_ROOT.glob("*.html")):
        parser = ResourceParser()
        parser.feed(page.read_text(encoding="utf-8"))
        assets: dict[str, int] = {page.name: page.stat().st_size}
        for reference in parser.references:
            path = _asset_path(reference)
            if path is None:
                continue
            key = path.relative_to(REPO_ROOT).as_posix()
            assets[key] = path.stat().st_size
            all_assets[key] = path.stat().st_size
        pages[page.name] = {
            "request_count": len(assets),
            "bytes": sum(assets.values()),
            "assets": assets,
        }

    cold_bytes = sum(int(item["bytes"]) for item in pages.values())
    unique_bytes = sum(all_assets.values())
    return {
        "pages": pages,
        "summary": {
            "page_count": len(pages),
            "unique_asset_count": len(all_assets),
            "cold_declared_bytes": cold_bytes,
            "unique_declared_bytes": unique_bytes,
            "repeat_page_reuse_potential_bytes": cold_bytes - unique_bytes,
            "repeat_page_reuse_potential_pct": round(
                (cold_bytes - unique_bytes) * 100 / cold_bytes, 2
            )
            if cold_bytes
            else 0,
        },
    }


def runtime_nav_audit() -> dict[str, object]:
    from server_harness import start_server
    from playwright.sync_api import sync_playwright

    results: dict[str, object] = {}
    with start_server() as server, sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            for page_file in sorted(p.name for p in REPO_ROOT.glob("*.html")):
                context = browser.new_context(service_workers="block")
                page = context.new_page()
                try:
                    page.goto(
                        f"{server.base_url}/{page_file}",
                        wait_until="domcontentloaded",
                        timeout=30_000,
                    )
                    page.wait_for_timeout(250)
                    links = page.locator(".nav-links a").evaluate_all(
                        "els => els.map(a => [a.getAttribute('href'), a.textContent.trim(), a.classList.contains('is-active')])"
                    )
                    expected_current = (
                        "derivatives-analytics.html"
                        if page_file == "derivatives-ai.html"
                        else page_file
                    )
                    expected = [
                        [href, label, href == expected_current]
                        for href, label in EXPECTED_NAV
                    ]
                    results[page_file] = {
                        "ok": links == expected,
                        "link_count": len(links),
                        "active_count": sum(1 for link in links if link[2]),
                        "expected_redirect": page_file == "derivatives-ai.html",
                    }
                finally:
                    context.close()
        finally:
            browser.close()
    return results


def runtime_cache_audit() -> dict[str, object]:
    """Measure the second-page static response reuse provided by the SW."""
    from server_harness import start_server
    from playwright.sync_api import sync_playwright

    static_suffixes = (".html", ".js", ".css", ".svg", ".png", ".webmanifest")
    responses: list[object] = []
    with start_server() as server, sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(service_workers="allow")
        page = context.new_page()
        try:
            page.goto(f"{server.base_url}/index.html", wait_until="load", timeout=30_000)
            page.wait_for_timeout(1_000)
            page.evaluate("navigator.serviceWorker.ready")

            def collect(response: object) -> None:
                url = response.url
                if url.startswith(server.base_url) and url.split("?", 1)[0].endswith(static_suffixes):
                    responses.append(response)

            page.on("response", collect)
            page.goto(f"{server.base_url}/bonds.html", wait_until="load", timeout=30_000)
            page.wait_for_timeout(500)
        finally:
            context.close()
            browser.close()

    hits = sum(1 for response in responses if response.from_service_worker)
    return {
        "second_page_static_response_count": len(responses),
        "service_worker_hit_count": hits,
        "service_worker_hit_rate_pct": round(hits * 100 / len(responses), 2) if responses else 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--skip-runtime-nav", action="store_true", help="only audit declared file payload"
    )
    args = parser.parse_args()
    report: dict[str, object] = {"declared_payload": declared_payload()}
    if not args.skip_runtime_nav:
        report["runtime_nav"] = runtime_nav_audit()
        report["runtime_cache"] = runtime_cache_audit()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not args.skip_runtime_nav:
        failed = [name for name, item in report["runtime_nav"].items() if not item["ok"]]
        if failed:
            print("RESOURCE_AUDIT_FAIL: " + ", ".join(failed), file=sys.stderr)
            return 1
    print("RESOURCE_AUDIT_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
