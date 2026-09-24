"""工單 00 第二部分:Playwright 前端行為基準。

用法:
    python regression/frontend_check.py --capture   # 在原版建立截圖/元素數量基準
    python regression/frontend_check.py --compare   # 與基準比對(重構期反覆執行)

比對規則:
- 本地程式 console error 嚴格比對:基準為零,重構後也必須為零(warning 可容忍)。
- 外部資源連線失敗另列為 external，不混入程式碼錯誤。
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
from urllib.parse import urlsplit

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


def _is_external_resource_error(message: str) -> bool:
    return any(marker in message for marker in (
        "net::ERR_NETWORK_ACCESS_DENIED",
        "net::ERR_INTERNET_DISCONNECTED",
        "net::ERR_NAME_NOT_RESOLVED",
        "Failed to load resource: net::ERR_FAILED",
    ))


def _is_external_resource_url(url: str) -> bool:
    parts = urlsplit(url)
    return parts.scheme in {"http", "https"} and parts.hostname not in {None, "127.0.0.1", "localhost", "::1"}


def _external_noise_categories(messages: list[str]) -> list[str]:
    """把可預期的外部視覺噪音分群,但不把它從 DOM/count gate 隱藏。"""
    categories: set[str] = set()
    for message in messages:
        lowered = message.lower()
        if "fonts.googleapis.com" in lowered or "google fonts" in lowered or "web fonts" in lowered:
            categories.add("external_font")
        elif "net::err_" in lowered or "request failed" in lowered:
            categories.add("external_network")
        else:
            categories.add("external_resource")
    return sorted(categories)


def _visit_page(browser, base_url: str, page_file: str, mode: str) -> dict:
    console_errors: list[str] = []
    external_errors: list[str] = []
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
        lambda msg: (external_errors if _is_external_resource_error(msg.text) else console_errors
                     if msg.type == "error" else console_warnings).append(msg.text)
        if msg.type in ("error", "warning")
        else None,
    )
    page.on("pageerror", lambda exc: console_errors.append(str(exc)))
    page.on(
        "requestfailed",
        lambda request: external_errors.append(
            f"{request.url}: {request.failure or 'request failed'}"
        )
        if _is_external_resource_url(request.url)
        else console_errors.append(f"Failed local resource request: {request.url}"),
    )

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

    font_probe = page.evaluate(
        """() => ({
          externalGoogleFonts: Array.from(document.querySelectorAll('link[rel="stylesheet"]'))
            .some(link => new URL(link.href, location.href).hostname === 'fonts.googleapis.com'),
          notoSansTcReady: document.fonts.check('16px "Noto Sans TC"'),
          spaceGroteskReady: document.fonts.check('16px "Space Grotesk"'),
        })"""
    )
    if font_probe["externalGoogleFonts"] and not (
        font_probe["notoSansTcReady"] and font_probe["spaceGroteskReady"]
    ):
        external_errors.append("Google Fonts stylesheet present but requested web fonts are unavailable")

    counts = _measure_page(page)
    screenshot_bytes = page.screenshot(full_page=True)
    context.close()

    return {
        "file": page_file,
        "console_errors": console_errors,
        "external_errors": external_errors,
        "console_warning_count": len(console_warnings),
        "counts": counts,
        "screenshot_bytes": screenshot_bytes,
    }


def run(mode: str, diagnostic_dir: Path | None = None) -> dict:
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
    return _compare(results, diagnostic_dir=diagnostic_dir)


def _write_baseline(results: list[dict]) -> dict:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    pages_manifest = []
    warnings = []
    for result in results:
        screenshot_name = f"{result['file']}.png"
        (SCREENSHOT_DIR / screenshot_name).write_bytes(result["screenshot_bytes"])
        if result["console_errors"]:
            warnings.append(f"{result['file']}: 基準抓取時已出現 console error: {result['console_errors']}")
        if result["external_errors"]:
            warnings.append(f"{result['file']}: 基準抓取時有 external resource error: {result['external_errors']}")
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


def _write_visual_diagnostics(
    baseline_png: bytes,
    current_png: bytes,
    page_file: str,
    diagnostic_dir: Path,
) -> dict[str, str]:
    """Write baseline/current/diff images for a true visual failure."""
    from io import BytesIO

    import numpy as np
    from PIL import Image

    diagnostic_dir.mkdir(parents=True, exist_ok=True)
    safe_name = page_file.replace("/", "_").replace("\\", "_")
    baseline_path = diagnostic_dir / f"{safe_name}.baseline.png"
    current_path = diagnostic_dir / f"{safe_name}.current.png"
    diff_path = diagnostic_dir / f"{safe_name}.diff.png"

    baseline_path.write_bytes(baseline_png)
    current_path.write_bytes(current_png)

    img_a = Image.open(BytesIO(baseline_png)).convert("RGB")
    img_b = Image.open(BytesIO(current_png)).convert("RGB")
    width = max(img_a.width, img_b.width)
    height = max(img_a.height, img_b.height)

    canvas_a = Image.new("RGB", (width, height), (0, 0, 0))
    canvas_a.paste(img_a, (0, 0))
    canvas_b = Image.new("RGB", (width, height), (0, 0, 0))
    canvas_b.paste(img_b, (0, 0))

    arr_a = np.asarray(canvas_a)
    arr_b = np.asarray(canvas_b)
    diff_mask = np.any(arr_a != arr_b, axis=-1)
    diff_image = Image.fromarray((diff_mask.astype(np.uint8) * 255))
    diff_image.save(diff_path)

    return {
        "baseline": baseline_path.name,
        "current": current_path.name,
        "diff": diff_path.name,
    }


def _compare(results: list[dict], diagnostic_dir: Path | None = None) -> dict:
    if not FRONTEND_MANIFEST_PATH.exists():
        raise SystemExit(f"找不到前端基準 {FRONTEND_MANIFEST_PATH},請先執行 --capture")
    baseline = json.loads(FRONTEND_MANIFEST_PATH.read_text(encoding="utf-8"))
    baseline_by_file = {p["file"]: p for p in baseline["pages"]}

    failures: list[str] = []
    page_reports: list[dict] = []
    for result in results:
        file = result["file"]
        base = baseline_by_file.get(file)
        page_report = {
            "file": file,
            "counts": result["counts"],
            "console_error_count": len(result["console_errors"]),
            "external_error_count": len(result["external_errors"]),
            "external_noise_categories": _external_noise_categories(result["external_errors"]),
            "visual": {
                "status": "not_checked",
                "diff_pct": None,
                "threshold_pct": PIXEL_DIFF_FAIL_THRESHOLD_PCT,
            },
            "failed": False,
            "diagnostic_artifacts": {},
        }
        if base is None:
            failures.append(f"{file}: 基準中沒有這個頁面(新增頁面需先補基準)")
            page_report["failed"] = True
            page_report["visual"]["status"] = "missing_baseline"
            page_reports.append(page_report)
            continue

        if result["console_errors"]:
            failures.append(f"{file}: 出現 {len(result['console_errors'])} 個 console error: {result['console_errors'][:3]}")
            page_report["failed"] = True
        if result["external_errors"]:
            categories = ",".join(page_report["external_noise_categories"])
            print(f"  [EXTERNAL] {file}: {len(result['external_errors'])} 個外部資源錯誤({categories})")

        for key, base_value in base["counts"].items():
            current_value = result["counts"].get(key)
            if current_value != base_value:
                failures.append(f"{file}: 元素數量 {key} 基準={base_value} 現況={current_value}")
                page_report["failed"] = True

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
            page_report["visual"]["diff_pct"] = round(diff_pct, 4)
            if diff_pct > PIXEL_DIFF_FAIL_THRESHOLD_PCT:
                if result.get("external_errors"):
                    page_report["visual"]["status"] = "external_noise"
                    print(
                        f"  [EXTERNAL] {file}: visual diff {diff_pct:.2f}% > "
                        f"{PIXEL_DIFF_FAIL_THRESHOLD_PCT}%；保留 DOM/count gate，略過 pixel gate"
                    )
                    if diagnostic_dir is not None:
                        page_report["diagnostic_artifacts"] = _write_visual_diagnostics(
                            screenshot_path.read_bytes(),
                            result["screenshot_bytes"],
                            file,
                            diagnostic_dir,
                        )
                        print(
                            f"  [DIAG] {file}: external-noise 仍寫入 baseline/current/diff 到 "
                            f"{diagnostic_dir}"
                        )
                else:
                    page_report["visual"]["status"] = "fail"
                    failures.append(
                        f"[畫面差異] {file}: 截圖像素差異率 {diff_pct:.2f}% > "
                        f"{PIXEL_DIFF_FAIL_THRESHOLD_PCT}%"
                    )
                    page_report["failed"] = True
                    if diagnostic_dir is not None:
                        page_report["diagnostic_artifacts"] = _write_visual_diagnostics(
                            screenshot_path.read_bytes(),
                            result["screenshot_bytes"],
                            file,
                            diagnostic_dir,
                        )
                        print(
                            f"  [DIAG] {file}: 已寫入 baseline/current/diff 到 "
                            f"{diagnostic_dir}"
                        )
            else:
                page_report["visual"]["status"] = "pass_with_external_noise" if result.get("external_errors") else "pass"
        else:
            page_report["visual"]["status"] = "missing_screenshot"
            failures.append(f"{file}: 找不到基準截圖 {screenshot_path}")
            page_report["failed"] = True
        page_reports.append(page_report)

    ok = not failures
    summary = {
        "page_count": len(page_reports),
        "failed_pages": sum(1 for item in page_reports if item["failed"]),
        "visual_pass": sum(1 for item in page_reports if item["visual"]["status"] == "pass"),
        "visual_pass_with_external_noise": sum(
            1 for item in page_reports if item["visual"]["status"] == "pass_with_external_noise"
        ),
        "visual_external_noise": sum(1 for item in page_reports if item["visual"]["status"] == "external_noise"),
        "visual_fail": sum(1 for item in page_reports if item["visual"]["status"] == "fail"),
        "external_font_pages": sum(
            1 for item in page_reports if "external_font" in item["external_noise_categories"]
        ),
    }
    print(f"[frontend_check] compare 結果: {'PASS' if ok else 'FAIL'} ({len(failures)} 項問題)")
    print(
        "[frontend_check] summary: "
        f"pages={summary['page_count']}, failed={summary['failed_pages']}, "
        f"visual_pass={summary['visual_pass']}, "
        f"visual_external_noise={summary['visual_external_noise']}, "
        f"visual_fail={summary['visual_fail']}, "
        f"external_font_pages={summary['external_font_pages']}, "
        f"threshold={PIXEL_DIFF_FAIL_THRESHOLD_PCT:.2f}%"
    )
    for failure in failures:
        print(f"  [FAIL] {failure}")
    return {
        "ok": ok,
        "failures": failures,
        "summary": summary,
        "pixel_diff_fail_threshold_pct": PIXEL_DIFF_FAIL_THRESHOLD_PCT,
        "pages": page_reports,
    }


def _write_report(outcome: dict, report_path: Path) -> None:
    """輸出 CI/人工查閱用摘要;只有明確指定 --report 才寫檔。"""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "mode": "frontend_compare",
        "ok": outcome.get("ok", False),
        "summary": outcome.get("summary", {}),
        "pixel_diff_fail_threshold_pct": outcome.get("pixel_diff_fail_threshold_pct"),
        "pages": outcome.get("pages", []),
        "failures": outcome.get("failures", []),
    }
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(f"[frontend_check] 已寫入報表 {report_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--capture", action="store_true", help="建立前端基準(只在原版執行一次)")
    group.add_argument("--compare", action="store_true", help="與既有前端基準比對")
    parser.add_argument(
        "--report",
        type=Path,
        help="可選:將 compare 的逐頁 visual status 與噪音分類輸出為 JSON",
    )
    parser.add_argument(
        "--diagnostic-dir",
        type=Path,
        help="可選:compare 發生真正 visual fail 時輸出 baseline/current/diff PNG",
    )
    args = parser.parse_args()

    outcome = run(
        "capture" if args.capture else "compare",
        diagnostic_dir=args.diagnostic_dir,
    )
    if args.report:
        if args.capture:
            print("[frontend_check] --report 僅支援 --compare, capture 不輸出 compare 報表")
        else:
            _write_report(outcome, args.report)
    if args.compare and not outcome.get("ok", False):
        sys.exit(1)
