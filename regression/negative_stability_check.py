"""Phase 4:負向情境與前端穩定性驗證。

用法:
    python regression/negative_stability_check.py --compare

檢查內容:
- 在既有 page-load HAR 重播下,將代表性 API 改成 502/503/504。
- 將成功回應改成 malformed JSON、缺欄位與空資料。
- 確認頁面仍進入 ESM runtime、顯示可辨識的 fallback/empty 狀態,且沒有
  未捕捉的 pageerror。
- 以短時間 synthetic endpoint 驗證 fetchWithTimeout 會回報 TIMEOUT。

所有注入都只存在於 Playwright route interception;不修改產品資料、HAR 或
baseline fixture,也不依賴外部網路。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

from server_harness import start_server


REGRESSION_DIR = Path(__file__).resolve().parent
REPO_ROOT = REGRESSION_DIR.parent
HAR_DIR = REGRESSION_DIR / "baseline" / "har"
FIXED_SERVER_PORT = 18768


class NegativeStabilityError(Exception):
    """Raised when a negative stability contract cannot be executed."""


def _har_path(page_file: str) -> Path:
    path = HAR_DIR / f"{page_file}.har"
    if not path.exists():
        raise NegativeStabilityError(f"{page_file}: 找不到 page-load HAR {path}")
    return path


def _wait_for_esm(page, timeout: int = 15000) -> None:
    page.wait_for_function(
        "expected => document.documentElement?.dataset.td02Esm === expected",
        arg="esm-active",
        timeout=timeout,
    )


def _body_text(page) -> str:
    return page.locator("body").inner_text(timeout=5000)


def _run_injected_case(browser, base_url: str, case: dict) -> str | None:
    context = browser.new_context()
    context.route_from_har(str(_har_path(case["page"])), url="**/api/**", not_found="abort")
    target_path = case.get("path")
    injected_body = case.get("body", "")
    injected_status = int(case.get("status", 200))

    def route_api(route) -> None:
        request_path = urlsplit(route.request.url).path
        if request_path == target_path:
            route.fulfill(
                status=injected_status,
                content_type="application/json",
                body=injected_body,
            )
            return
        route.fallback()

    context.route("**/api/**", route_api)
    page = context.new_page()
    page_errors: list[str] = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))

    failures: list[str] = []
    try:
        page.goto(
            f"{base_url}/{case['page']}",
            wait_until="domcontentloaded",
            timeout=30000,
        )
        _wait_for_esm(page)
        page.wait_for_function(
            "selector => Boolean(document.querySelector(selector)?.innerText?.trim())",
            arg=case.get("root_selector", "main"),
            timeout=15000,
        )
        page.wait_for_timeout(250)
        text = _body_text(page)
        for marker in case.get("expected_markers", []):
            if marker not in text:
                failures.append(f"缺少 fallback marker={marker!r}, body={text[:240]!r}")
        if page_errors:
            failures.append(f"pageerror={page_errors[:3]!r}")
    except Exception as exc:  # noqa: BLE001
        failures.append(f"case exception: {exc}")
    finally:
        context.close()

    if failures:
        return f"{case['name']}: " + "; ".join(failures[:4])
    return None


def _run_timeout_case(browser, base_url: str) -> str | None:
    context = browser.new_context()
    context.route_from_har(str(_har_path("bonds.html")), url="**/api/**", not_found="abort")

    def delayed_route(route) -> None:
        time.sleep(0.25)
        route.fulfill(status=200, content_type="application/json", body="{}")

    context.route("**/negative-timeout", delayed_route)
    page = context.new_page()
    page_errors: list[str] = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    try:
        page.goto(f"{base_url}/bonds.html", wait_until="domcontentloaded", timeout=30000)
        _wait_for_esm(page)
        result = page.evaluate(
            """
            async () => {
              try {
                await fetchWithTimeout('/negative-timeout', {}, 50);
                return { ok: false, code: null, message: 'resolved unexpectedly' };
              } catch (error) {
                return { ok: true, code: error?.code || null, message: error?.message || String(error) };
              }
            }
            """
        )
        if result != {"ok": True, "code": "TIMEOUT", "message": "TIMEOUT"}:
            return f"synthetic timeout: result={result!r}, expected TIMEOUT"
        if page_errors:
            return f"synthetic timeout: pageerror={page_errors[:3]!r}"
    except Exception as exc:  # noqa: BLE001
        return f"synthetic timeout: case exception: {exc}"
    finally:
        context.close()
    return None


def run() -> dict[str, object]:
    from playwright.sync_api import sync_playwright

    cases = [
        {
            "name": "bonds-502",
            "page": "bonds.html",
            "path": "/api/global-market/bonds",
            "status": 502,
            "body": json.dumps({"success": False, "error_code": "UPSTREAM_BAD_GATEWAY"}),
            "expected_markers": ["債券資料暫時無法載入"],
        },
        {
            "name": "us-stocks-503",
            "page": "us-stocks.html",
            "path": "/api/global-market/us-stocks",
            "status": 503,
            "body": json.dumps({"success": False, "error_code": "UPSTREAM_UNAVAILABLE"}),
            "expected_markers": ["線上資料暫時無法載入"],
        },
        {
            "name": "us-overview-504",
            "page": "us-market-overview.html",
            "path": "/api/global-market/us-stocks",
            "status": 504,
            "body": json.dumps({"success": False, "error_code": "UPSTREAM_TIMEOUT"}),
            "expected_markers": ["線上資料暫時無法載入"],
        },
        {
            "name": "bonds-malformed-json",
            "page": "bonds.html",
            "path": "/api/global-market/bonds",
            "status": 200,
            "body": "{",
            "expected_markers": ["債券資料暫時無法載入"],
        },
        {
            "name": "bonds-missing-fields",
            "page": "bonds.html",
            "path": "/api/global-market/bonds",
            "status": 200,
            "body": json.dumps({"category": "bonds"}),
            "expected_markers": ["債券研究區"],
        },
        {
            "name": "bonds-empty-data",
            "page": "bonds.html",
            "path": "/api/global-market/bonds",
            "status": 200,
            "body": json.dumps({"category": "bonds", "items": [], "summary": {}}),
            "expected_markers": ["債券研究區"],
        },
    ]
    failures: list[str] = []
    with start_server(port=FIXED_SERVER_PORT) as server, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            for case in cases:
                failure = _run_injected_case(browser, server.base_url, case)
                if failure:
                    failures.append(failure)
            timeout_failure = _run_timeout_case(browser, server.base_url)
            if timeout_failure:
                failures.append(timeout_failure)
        finally:
            browser.close()
    return {"ok": not failures, "failures": failures, "case_count": len(cases) + 1}


def main() -> int:
    parser = argparse.ArgumentParser(description="驗證負向 API 情境與前端穩定性")
    parser.add_argument("--compare", action="store_true", help="執行負向情境與穩定性驗證")
    args = parser.parse_args()
    if not args.compare:
        parser.error("請指定 --compare")

    try:
        result = run()
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] negative stability contract: {exc}")
        return 1

    if not result["ok"]:
        print("[FAIL] negative stability contract")
        for failure in result["failures"]:
            print(f"  - {failure}")
        return 1

    print(f"[PASS] negative stability contract: {result['case_count']} cases, no pageerror")
    return 0


if __name__ == "__main__":
    sys.exit(main())
