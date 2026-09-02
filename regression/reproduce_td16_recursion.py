"""TD-16 Part 1: reproduce the loadInstitutionalTradeHistoryIfNeeded infinite recursion.

Root cause (js/stock-detail.js): loadInstitutionalTradeHistoryIfNeeded() only stops
recursing when history.rows.length >= 5 (line 86). Any fetched/cached history with
fewer than 5 rows (including 0, or a missing/null history object) fails that check,
falls into the cache-hit branch (lines 89-98) or the fetch-success branch (lines
113-124), both of which unconditionally call renderStockDetail(nextDetail) -
renderStockDetail unconditionally calls loadInstitutionalTradeHistoryIfNeeded(detail)
again near its end (line 2476). Once the response is cached, this becomes a tight
synchronous renderStockDetail -> loadInstitutionalTradeHistoryIfNeeded -> renderStockDetail
loop with no termination condition.

In practice this is not a quick, cleanly-catchable RangeError: each recursive frame
runs the FULL renderStockDetail() (2500+ lines: DOM rebuild, chart rendering, event
binding), so the tab's render thread gets pegged solid and stops responding to CDP
commands entirely - a genuine browser-level hang, confirmed by direct testing (a
naive in-process Playwright reproduction attempt hung past 120s with zero output).

To make this reproducible without risking the whole test run hanging, each case runs
in its own subprocess with a hard wall-clock timeout (--case-worker below). A timeout
is itself treated as "crashed" (it is - the tab became unresponsive), not as an
inconclusive result.

Usage:
    python regression/reproduce_td16_recursion.py

This asserts the end state for every case: the page must render the stock
detail without crashing/hanging, regardless of how many institutional history
rows come back (0, <5, exactly 5, missing, or a normal count). The fixture
also mocks the initial live-search and stock-detail responses so the test
reaches the institutional-history branch deterministically instead of being
blocked by unrelated external data-source availability.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REGRESSION_DIR = Path(__file__).resolve().parent
PORT_BASE = 18900

# Desired end state for every case, boundary and normal alike: the page renders
# without crashing/hanging. None of these should ever legitimately crash - a
# stock genuinely having <5 days of institutional trade history (new listing,
# thinly traded) is normal, valid data, not an error condition.
CASES = [
    {"label": "0 rows (empty array)", "rows": 0},
    {"label": "2 rows (typical <5)", "rows": 2},
    {"label": "4 rows (boundary -1)", "rows": 4},
    {"label": "missing/null history", "rows": None},
    {"label": "5 rows (exact boundary)", "rows": 5},
    {"label": "10 rows (normal case)", "rows": 10},
]


def make_history_body(rows):
    if rows is None:
        payload = {"institutionalTrades": None}
    else:
        payload = {
            "institutionalTradeHistory": {
                "rows": [
                    {
                        "date": f"2026-01-{i:02d}", "label": f"01/{i:02d}", "changePct": 0.0,
                        "dealerLotsValue": 0.0, "dealerValue": 0.0, "foreignChipRatio": 0.0,
                        "foreignLotsValue": 0.0, "foreignValue": 0.0, "totalLotsValue": 0.0,
                        "totalValue": 0.0, "trustLotsValue": 0.0, "trustValue": 0.0, "volume": 0.0,
                    }
                    for i in range(1, rows + 1)
                ],
            },
            "institutionalTrades": None,
        }
    return json.dumps(payload)


def make_live_search_body():
    return json.dumps({
        "results": [{
            "code": "2330", "name": "台積電", "market": "TWSE", "marketLabel": "上市",
            "close": "600", "change": "+10", "pct": "+1.69%", "volume": "1000",
        }],
        "count": 1, "snapshotDate": "2026-01-10", "refreshedAt": "2026-01-10 12:00:00",
    }, ensure_ascii=False)


def make_detail_body():
    history = [
        {"date": "2026-01-09", "open": 590, "high": 595, "low": 585, "close": 590, "change": 0, "volume": 100},
        {"date": "2026-01-10", "open": 590, "high": 605, "low": 590, "close": 600, "change": 10, "volume": 1000},
    ]
    return json.dumps({
        "code": "2330", "name": "台積電", "market": "TWSE", "close": "600", "value": "600",
        "change": "+10", "pct": "+1.69%", "open": "590", "high": "605", "low": "590",
        "volume": "1000", "snapshotDate": "2026-01-10", "cachedAt": "2026-01-10 12:00:00",
        "historyDays": history, "recentDays": history, "historyCount": len(history),
        "historyStartDate": "2026-01-09", "historyEndDate": "2026-01-10",
        "institutionalTradeHistory": {}, "institutionalTrades": {},
        "chartIntervals": {"supported": ["day", "week", "month"], "intradayAvailable": False},
    }, ensure_ascii=False)


def worker_main(rows_arg: str, port: int) -> None:
    sys.path.insert(0, str(REGRESSION_DIR))
    from server_harness import start_server  # noqa: E402
    from playwright.sync_api import sync_playwright  # noqa: E402

    rows = None if rows_arg == "None" else int(rows_arg)
    body = make_history_body(rows)
    live_search_body = make_live_search_body()
    detail_body = make_detail_body()

    handle = start_server(port=port)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            context = browser.new_context()
            page = context.new_page()
            page.set_default_timeout(8000)
            console_errors: list[str] = []
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
            page.on("pageerror", lambda exc: console_errors.append(str(exc)))

            def handle_route(route):
                url = route.request.url
                if "institutional-history" in url:
                    route.fulfill(status=200, content_type="application/json", body=body)
                elif "/api/twse/live-search" in url:
                    route.fulfill(status=200, content_type="application/json", body=live_search_body)
                elif "/api/twse/stock/2330" in url:
                    route.fulfill(status=200, content_type="application/json", body=detail_body)
                elif url.endswith("/twse-data.js"):
                    route.fulfill(status=200, content_type="application/javascript", body="window.TWSE_DATA = {}; window.TWSE_ALL_STOCKS = [];")
                else:
                    route.continue_()

            page.route("**/*", handle_route)
            page.goto(f"{handle.base_url}/tw-stock-search.html", wait_until="load", timeout=15000)
            page.fill("#stock-search-input", "2330")
            page.click("#stock-search-form button[type=submit]")
            page.wait_for_timeout(4000)
            detail_len = len(page.eval_on_selector("#stock-detail", "el => el.innerHTML") or "")
            browser.close()
            crashed = detail_len < 200 or any(
                "Maximum call stack size exceeded" in e or "RangeError" in e for e in console_errors
            )
            print(json.dumps({"crashed": crashed, "detail_len": detail_len, "console_errors": console_errors[:5]}))
    finally:
        handle.stop()


def run_case_in_subprocess(case: dict, port: int, timeout_s: float = 25.0) -> tuple[bool, str]:
    rows_arg = "None" if case["rows"] is None else str(case["rows"])
    try:
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--case-worker", rows_arg, str(port)],
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return True, "TIMEOUT (tab became unresponsive - treated as crash)"

    last_line = ""
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith("{"):
            last_line = line
    if not last_line:
        return True, f"no structured output; exit={result.returncode}; stderr_tail={result.stderr[-500:]}"
    data = json.loads(last_line)
    detail = f"detail_len={data['detail_len']}, console_errors={data['console_errors']}"
    return data["crashed"], detail


def main() -> None:
    failures = []
    for i, case in enumerate(CASES):
        crashed, detail = run_case_in_subprocess(case, PORT_BASE + i)
        status = "CRASH" if crashed else "OK"
        result = "FAIL" if crashed else "PASS"
        print(f"[{result}] {case['label']}: page must not crash -> observed={status}")
        print(f"    {detail}")
        if crashed:
            failures.append(case["label"])

    if failures:
        print(f"\nTD16_REPRODUCE_FAIL: {len(failures)} case(s) crashed (bug reproduced): {failures}")
        raise SystemExit(1)
    print("\nTD16_REPRODUCE_PASS: no case crashed (bug fixed / not present)")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--case-worker":
        worker_main(sys.argv[2], int(sys.argv[3]))
    else:
        main()
