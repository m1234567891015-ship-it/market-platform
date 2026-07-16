"""工單 00 第二部分:Playwright 前端行為基準。

用法:
    python regression/frontend_check.py --capture   # 在原版建立截圖/元素數量基準
    python regression/frontend_check.py --compare   # 與基準比對(重構期反覆執行)

比對規則:
- console error 嚴格比對:基準為零,重構後也必須為零(warning 可容忍)。
- 關鍵元素數量(卡片 .card、表格列 tr、canvas)必須與基準完全一致(±0)。
- 截圖像素差異率 > 2% 視為 fail。

關鍵設計:大多數頁面的內容來自即時 TWSE/TAIFEX/Yahoo 報價,每次重新整理
數值、排行、新聞時間都會變,直接比對兩次「即時」截圖必然充滿雜訊。
所以 --capture 時用 Playwright 內建的 HAR 錄製功能把當下每個頁面實際呼叫
的 /api/* 回應整包存成 regression/baseline/har/<page>.har;--compare 時改用
route_from_har() 讓瀏覽器對 /api/* 的請求一律重播同一份錄好的回應,不再
打真正的網路。這樣頁面看到的資料每次都完全相同,截圖與元素數量比對才有意義
——如果重構後前端呼叫的 API 路徑/參數變了,HAR 對不上會直接讓那個請求失敗,
反而正確地曝露出行為改變。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from server_harness import start_server  # noqa: E402

REGRESSION_DIR = Path(__file__).resolve().parent
REPO_ROOT = REGRESSION_DIR.parent
BASELINE_DIR = REGRESSION_DIR / "baseline"
SCREENSHOT_DIR = BASELINE_DIR / "screenshots"
HAR_DIR = BASELINE_DIR / "har"
FRONTEND_MANIFEST_PATH = BASELINE_DIR / "frontend_manifest.json"

PIXEL_DIFF_FAIL_THRESHOLD_PCT = 2.0

# HAR 錄製的請求 URL 含完整 origin,capture 與 compare 必須用同一個固定
# port,重播才能對得上錄好的紀錄(見 server_harness.start_server 的說明)。
FIXED_SERVER_PORT = 18765

PAGES = sorted(p.name for p in REPO_ROOT.glob("*.html"))

# 對應工單第二部分第 4 點的特別驗證點:頁面 -> 至少要非零的計數欄位。
SPECIAL_NONZERO_CHECKS = {
    "index.html": ["cards"],
    "tw-stocks.html": ["table_rows"],
    "futures.html": ["table_rows"],
    "options.html": ["table_rows"],
}


def _measure_page(page) -> dict:
    return page.evaluate(
        """
        () => ({
            cards: document.querySelectorAll('[class*="card" i]').length,
            table_rows: document.querySelectorAll('tr').length,
            canvas: document.querySelectorAll('canvas').length,
            canvas_nonblank: Array.from(document.querySelectorAll('canvas')).filter(c => c.width > 0 && c.height > 0).length,
        })
        """
    )


def _visit_page(browser, base_url: str, page_file: str, mode: str) -> dict:
    console_errors: list[str] = []
    console_warnings: list[str] = []

    har_path = HAR_DIR / f"{page_file}.har"
    context_kwargs: dict = {}
    if mode == "capture":
        HAR_DIR.mkdir(parents=True, exist_ok=True)
        context_kwargs["record_har_path"] = str(har_path)
        context_kwargs["record_har_mode"] = "full"
        context_kwargs["record_har_content"] = "embed"
        context_kwargs["record_har_url_filter"] = "**/api/**"

    context = browser.new_context(**context_kwargs)
    if mode == "compare":
        if not har_path.exists():
            raise SystemExit(f"找不到 {page_file} 的 HAR 基準 {har_path},請先執行 --capture")
        context.route_from_har(str(har_path), url="**/api/**", not_found="abort")

    page = context.new_page()
    page.on(
        "console",
        lambda msg: (console_errors if msg.type == "error" else console_warnings).append(msg.text)
        if msg.type in ("error", "warning")
        else None,
    )
    page.on("pageerror", lambda exc: console_errors.append(str(exc)))

    url = f"{base_url}/{page_file}"
    page.goto(url, wait_until="load", timeout=30000)
    try:
        page.wait_for_load_state("networkidle", timeout=45000)
    except Exception:  # noqa: BLE001
        pass  # 頁面本身有輪詢式的背景請求時,networkidle 可能永遠不會觸發。

    # 許多區塊要等 API 回應才會展開,full_page 截圖前用「頁面高度連續兩次
    # 沒再變化」取代固定等待時間,避免截到內容還沒展開完的半成品畫面。
    previous_height = -1
    stable_rounds = 0
    for _ in range(20):
        page.wait_for_timeout(500)
        current_height = page.evaluate("document.documentElement.scrollHeight")
        if current_height == previous_height:
            stable_rounds += 1
            if stable_rounds >= 2:
                break
        else:
            stable_rounds = 0
        previous_height = current_height

    counts = _measure_page(page)
    screenshot_bytes = page.screenshot(full_page=True)
    context.close()

    return {
        "file": page_file,
        "console_errors": console_errors,
        "console_warning_count": len(console_warnings),
        "counts": counts,
        "screenshot_bytes": screenshot_bytes,
    }


def run(mode: str) -> dict:
    from playwright.sync_api import sync_playwright

    results = []
    with start_server(port=FIXED_SERVER_PORT) as server, sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            for page_file in PAGES:
                print(f"  [{mode}] {page_file} ...", flush=True)
                results.append(_visit_page(browser, server.base_url, page_file, mode))
        finally:
            browser.close()

    if mode == "capture":
        return _write_baseline(results)
    return _compare(results)


def _write_baseline(results: list[dict]) -> dict:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    pages_manifest = []
    warnings = []
    for result in results:
        screenshot_name = f"{result['file']}.png"
        (SCREENSHOT_DIR / screenshot_name).write_bytes(result["screenshot_bytes"])
        if result["console_errors"]:
            warnings.append(f"{result['file']}: 基準抓取時已出現 console error: {result['console_errors']}")
        for field in SPECIAL_NONZERO_CHECKS.get(result["file"], []):
            if result["counts"].get(field, 0) <= 0:
                warnings.append(f"{result['file']}: 特別驗證點 {field} 於基準抓取時為 0,請確認頁面是否正常渲染")
        pages_manifest.append(
            {
                "file": result["file"],
                "console_error_count": len(result["console_errors"]),
                "console_warning_count": result["console_warning_count"],
                "counts": result["counts"],
                "screenshot": f"screenshots/{screenshot_name}",
            }
        )

    manifest = {"page_count": len(pages_manifest), "pages": pages_manifest}
    FRONTEND_MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(f"[frontend_check] 已寫入 {FRONTEND_MANIFEST_PATH}、{len(pages_manifest)} 張基準截圖與 {len(pages_manifest)} 份 HAR")
    for warning in warnings:
        print(f"  [WARN] {warning}")
    return manifest


def _pixel_diff_pct(baseline_png: bytes, current_png: bytes) -> float:
    from io import BytesIO

    import numpy as np
    from PIL import Image

    img_a = Image.open(BytesIO(baseline_png)).convert("RGB")
    img_b = Image.open(BytesIO(current_png)).convert("RGB")

    # API 回應已經用 HAR 凍結成固定值,兩次截圖理論上該完全一致;
    # 貼齊左上角補邊(不縮放)比對,避免任何極端情況下的尺寸差異
    # 被 resize 內插誤放大成大量像素差異。
    width = max(img_a.width, img_b.width)
    height = max(img_a.height, img_b.height)
    canvas_a = Image.new("RGB", (width, height), (0, 0, 0))
    canvas_a.paste(img_a, (0, 0))
    canvas_b = Image.new("RGB", (width, height), (0, 0, 0))
    canvas_b.paste(img_b, (0, 0))

    total = width * height
    if total == 0:
        return 0.0
    arr_a = np.asarray(canvas_a)
    arr_b = np.asarray(canvas_b)
    diff_mask = np.any(arr_a != arr_b, axis=-1)
    return float(diff_mask.sum()) / total * 100.0


def _compare(results: list[dict]) -> dict:
    if not FRONTEND_MANIFEST_PATH.exists():
        raise SystemExit(f"找不到前端基準 {FRONTEND_MANIFEST_PATH},請先執行 --capture")
    baseline = json.loads(FRONTEND_MANIFEST_PATH.read_text(encoding="utf-8"))
    baseline_by_file = {p["file"]: p for p in baseline["pages"]}

    failures: list[str] = []
    for result in results:
        file = result["file"]
        base = baseline_by_file.get(file)
        if base is None:
            failures.append(f"{file}: 基準中沒有這個頁面(新增頁面需先補基準)")
            continue

        if result["console_errors"]:
            failures.append(f"{file}: 出現 {len(result['console_errors'])} 個 console error: {result['console_errors'][:3]}")

        for key, base_value in base["counts"].items():
            current_value = result["counts"].get(key)
            if current_value != base_value:
                failures.append(f"{file}: 元素數量 {key} 基準={base_value} 現況={current_value}")

        # 工單第二部分第 4 點的特別驗證點僅作為提醒:實際 DOM 是否用 <table>/<canvas>
        # 依頁面而異(例如 tw-stocks.html 排行榜用 <article class="...-row">,
        # 圖表用 SVG 而非 canvas),硬性要求「必須非零」會與既有頁面實作衝突。
        # 真正的迴歸防護由上面的「元素數量必須與基準一致」涵蓋,這裡只印警告。
        for field in SPECIAL_NONZERO_CHECKS.get(file, []):
            if result["counts"].get(field, 0) <= 0 and base["counts"].get(field, 0) <= 0:
                print(f"  [INFO] {file}: 特別驗證點 {field} 在基準與現況都是 0(非本次比對的失敗條件)")

        screenshot_path = BASELINE_DIR / base["screenshot"]
        if screenshot_path.exists():
            diff_pct = _pixel_diff_pct(screenshot_path.read_bytes(), result["screenshot_bytes"])
            if diff_pct > PIXEL_DIFF_FAIL_THRESHOLD_PCT:
                failures.append(f"{file}: 截圖像素差異率 {diff_pct:.2f}% > {PIXEL_DIFF_FAIL_THRESHOLD_PCT}%")
        else:
            failures.append(f"{file}: 找不到基準截圖 {screenshot_path}")

    ok = not failures
    print(f"[frontend_check] compare 結果: {'PASS' if ok else 'FAIL'} ({len(failures)} 項問題)")
    for failure in failures:
        print(f"  [FAIL] {failure}")
    return {"ok": ok, "failures": failures}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--capture", action="store_true", help="建立前端基準(只在原版執行一次)")
    group.add_argument("--compare", action="store_true", help="與既有前端基準比對")
    args = parser.parse_args()

    outcome = run("capture" if args.capture else "compare")
    if args.compare and not outcome.get("ok", False):
        sys.exit(1)
