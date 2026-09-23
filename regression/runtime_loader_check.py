"""Phase 3:驗證 21 頁 ESM runtime 與 classic fallback loader。

用法:
    python regression/runtime_loader_check.py

檢查內容:
- 21 個 HTML 都使用同一個 loader build version。
- 正常載入時每頁都進入 data-td02-esm=esm-active。
- 正常載入時 ESM module request 成功，且不意外載入 classic fallback。
- module 被刻意阻斷時，loader 會進入 classic-fallback 並載入 common/route fallback。

API request 使用 page-load HAR 重播；本檢查不打外部網路，也不修改任何基準檔。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from server_harness import start_server


REGRESSION_DIR = Path(__file__).resolve().parent
REPO_ROOT = REGRESSION_DIR.parent
HAR_DIR = REGRESSION_DIR / "baseline" / "har"
LOADER_PATH = REPO_ROOT / "market-pulse-esm-loader.js"
FIXED_SERVER_PORT = 18767
EXPECTED_PAGE_COUNT = 21


class RuntimeContractError(Exception):
    """Raised when a runtime or loader contract is violated."""


def _loader_version() -> str:
    source = LOADER_PATH.read_text(encoding="utf-8")
    match = re.search(r'CURRENT_BUILD_VERSION\s*=\s*["\']([^"\']+)["\']', source)
    if not match:
        raise RuntimeContractError("loader 找不到 CURRENT_BUILD_VERSION")
    return match.group(1)


def _page_files() -> list[str]:
    pages = sorted(path.name for path in REPO_ROOT.glob("*.html"))
    if len(pages) != EXPECTED_PAGE_COUNT:
        raise RuntimeContractError(
            f"HTML 頁面數量為 {len(pages)}，預期為 {EXPECTED_PAGE_COUNT}"
        )
    return pages


def _static_loader_versions(pages: list[str]) -> dict[str, str]:
    versions: dict[str, str] = {}
    pattern = re.compile(
        r'<script[^>]+src=["\']market-pulse-esm-loader\.js\?v=([^"\']+)["\']',
        re.IGNORECASE,
    )
    for page in pages:
        source = (REPO_ROOT / page).read_text(encoding="utf-8")
        matches = pattern.findall(source)
        if len(matches) != 1:
            raise RuntimeContractError(
                f"{page}: loader script 數量為 {len(matches)}，預期為 1"
            )
        versions[page] = matches[0]
    return versions


def _api_har_path(page: str) -> Path:
    path = HAR_DIR / f"{page}.har"
    if not path.exists():
        raise RuntimeContractError(f"{page}: 找不到 page-load HAR {path}")
    return path


def _loader_asset_path(url: str) -> str:
    return urlsplit(url).path.rsplit("/", 1)[-1]


def _wait_for_state(page, state: str, timeout: int = 15000) -> None:
    page.wait_for_function(
        "expected => document.documentElement?.dataset.td02Esm === expected",
        arg=state,
        timeout=timeout,
    )


def _normal_page_check(browser, server_base_url: str, page_file: str, version: str) -> str | None:
    context = browser.new_context()
    context.route_from_har(str(_api_har_path(page_file)), url="**/api/**", not_found="abort")
    page = context.new_page()
    requests: list[str] = []
    responses: dict[str, list[int]] = {}
    failures: list[str] = []

    page.on(
        "request",
        lambda request: requests.append(request.url)
        if _loader_asset_path(request.url)
        in {
            "market-pulse-esm-loader.js",
            "market-pulse-esm.min.js",
            "common-runtime.min.js",
            "route-bundle.min.js",
            "derivatives-status-addon.min.js",
        }
        else None,
    )
    page.on(
        "response",
        lambda response: responses.setdefault(_loader_asset_path(response.url), []).append(response.status)
        if _loader_asset_path(response.url)
        in {
            "market-pulse-esm-loader.js",
            "market-pulse-esm.min.js",
            "common-runtime.min.js",
            "route-bundle.min.js",
            "derivatives-status-addon.min.js",
        }
        else None,
    )
    page.on(
        "requestfailed",
        lambda request: failures.append(f"asset request failed: {request.url}")
        if _loader_asset_path(request.url)
        in {
            "market-pulse-esm-loader.js",
            "market-pulse-esm.min.js",
            "common-runtime.min.js",
            "route-bundle.min.js",
            "derivatives-status-addon.min.js",
        }
        else None,
    )
    page.on(
        "console",
        lambda message: failures.append(f"loader console error: {message.text}")
        if message.type == "error"
        and any(
            marker in message.text
            for marker in ("[Market Pulse]", "module script", "ESM", "fallback")
        )
        else None,
    )
    page.on(
        "pageerror",
        lambda error: failures.append(f"loader page error: {error}")
        if any(marker in str(error) for marker in ("module", "ESM", "fallback", "Market Pulse"))
        else None,
    )

    try:
        page.goto(f"{server_base_url}/{page_file}", wait_until="domcontentloaded", timeout=30000)
        if page_file == "derivatives-ai.html":
            page.wait_for_url(
                "**/derivatives-analytics.html#derivatives-analytics-market-state",
                timeout=15000,
            )
        _wait_for_state(page, "esm-active")
        loader_state = page.evaluate("() => document.documentElement?.dataset.td02Esm || null")
        if loader_state != "esm-active":
            failures.append(f"runtime state={loader_state!r}, expected 'esm-active'")

        module_urls = [url for url in requests if _loader_asset_path(url) == "market-pulse-esm.min.js"]
        minimum_module_requests = 2 if page_file == "derivatives-ai.html" else 1
        if len(module_urls) < minimum_module_requests:
            failures.append(
                f"ESM module request count={len(module_urls)}, expected >= {minimum_module_requests}"
            )
        else:
            module_versions = {
                parse_qs(urlsplit(url).query).get("v", [None])[0]
                for url in module_urls
            }
            if module_versions != {version}:
                failures.append(
                    f"ESM module versions={sorted(module_versions)!r}, expected [{version!r}]"
                )
        for fallback_name in ("common-runtime.min.js", "route-bundle.min.js", "derivatives-status-addon.min.js"):
            if any(_loader_asset_path(url) == fallback_name for url in requests):
                failures.append(f"正常 ESM 載入時意外載入 fallback: {fallback_name}")
        for asset_name in ("market-pulse-esm-loader.js", "market-pulse-esm.min.js"):
            statuses = responses.get(asset_name, [])
            if not statuses or any(status != 200 for status in statuses):
                failures.append(f"{asset_name} response statuses={statuses}, expected all 200")
    except Exception as exc:  # noqa: BLE001
        failures.append(f"runtime check exception: {exc}")
    finally:
        context.close()

    if failures:
        return f"{page_file}: " + "; ".join(failures[:5])
    return None


def _fallback_check(browser, server_base_url: str, page_file: str) -> str | None:
    context = browser.new_context()
    context.route_from_har(str(_api_har_path(page_file)), url="**/api/**", not_found="abort")
    context.route("**/market-pulse-esm.min.js**", lambda route: route.abort())
    page = context.new_page()
    requests: list[str] = []
    failures: list[str] = []
    page.on(
        "request",
        lambda request: requests.append(request.url)
        if _loader_asset_path(request.url)
        in {"market-pulse-esm.min.js", "common-runtime.min.js", "route-bundle.min.js"}
        else None,
    )
    page.on(
        "requestfailed",
        lambda request: failures.append(request.url)
        if _loader_asset_path(request.url) in {"common-runtime.min.js", "route-bundle.min.js"}
        else None,
    )

    try:
        page.goto(f"{server_base_url}/{page_file}", wait_until="domcontentloaded", timeout=30000)
        _wait_for_state(page, "classic-fallback")
        page.wait_for_function(
            "() => Array.from(document.scripts).some(script => script.src.includes('common-runtime.min.js'))",
            timeout=15000,
        )
        page.wait_for_function(
            "() => Array.from(document.scripts).some(script => script.src.includes('route-bundle.min.js'))",
            timeout=15000,
        )
        if not any(_loader_asset_path(url) == "market-pulse-esm.min.js" for url in requests):
            return f"{page_file}: synthetic module failure did not issue ESM request"
        for fallback_name in ("common-runtime.min.js", "route-bundle.min.js"):
            if not any(_loader_asset_path(url) == fallback_name for url in requests):
                return f"{page_file}: classic fallback did not request {fallback_name}"
        if failures:
            return f"{page_file}: fallback asset request failed: {failures[:2]}"
    except Exception as exc:  # noqa: BLE001
        return f"{page_file}: fallback check exception: {exc}"
    finally:
        context.close()
    return None


def run() -> dict[str, object]:
    from playwright.sync_api import sync_playwright

    pages = _page_files()
    version = _loader_version()
    static_versions = _static_loader_versions(pages)
    failures: list[str] = []
    for page, page_version in static_versions.items():
        if page_version != version:
            failures.append(f"{page}: HTML loader version={page_version!r}, expected {version!r}")

    with start_server(port=FIXED_SERVER_PORT) as server, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            for page in pages:
                failure = _normal_page_check(browser, server.base_url, page, version)
                if failure:
                    failures.append(failure)
            fallback_failure = _fallback_check(browser, server.base_url, "bonds.html")
            if fallback_failure:
                failures.append(fallback_failure)
        finally:
            browser.close()

    return {"ok": not failures, "failures": failures, "page_count": len(pages), "version": version}


def main() -> int:
    parser = argparse.ArgumentParser(description="驗證 21 頁 ESM runtime 與 classic fallback loader")
    parser.add_argument("--compare", action="store_true", help="執行 runtime/loader 驗證")
    args = parser.parse_args()
    if not args.compare:
        parser.error("請指定 --compare")

    try:
        result = run()
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] runtime loader contract: {exc}")
        return 1

    if not result["ok"]:
        print("[FAIL] runtime loader contract")
        for failure in result["failures"]:
            print(f"  - {failure}")
        return 1

    print(
        f"[PASS] runtime loader contract: {result['page_count']}/{EXPECTED_PAGE_COUNT} 頁, "
        f"version={result['version']}, normal ESM + synthetic fallback"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
