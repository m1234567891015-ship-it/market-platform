"""TD-18 H-10-03: isolated index/futures shadow canary.

The canary serves temporary copies of index.html and futures.html.  It never
rewrites production HTML/assets and never writes baseline files.  Each page is
checked first with the current classic scripts and then with H-10-01 shadow
bundles against the existing HAR/API and screenshot baselines.
"""
from __future__ import annotations

import gzip
import json
import mimetypes
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

REGRESSION_DIR = Path(__file__).resolve().parent
ROOT = REGRESSION_DIR.parent
BASELINE_DIR = REGRESSION_DIR / "baseline"
FRONTEND_HAR_DIR = BASELINE_DIR / "har"
INTERACTION_HAR_DIR = BASELINE_DIR / "interactions" / "har"
FRONTEND_MANIFEST = BASELINE_DIR / "frontend_manifest.json"
SCREENSHOT_DIR = BASELINE_DIR / "screenshots"
LOCKFILE = REGRESSION_DIR / "td18_shadow_build.lock.json"
BUILDER = REGRESSION_DIR / "td18_shadow_build.js"

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(REGRESSION_DIR))

from frontend_check import _measure_page, _pixel_diff_pct  # noqa: E402
from interaction_check import (  # noqa: E402
    _background_route_handler,
    _is_expected_background_error,
    _is_external_resource_error,
    run_render_only_step,
    _wait_dom_stable,
    run_step,
)
from interaction_specs import FUTURES, INDEX  # noqa: E402

CANARY_PAGES = (INDEX, FUTURES)
PAGE_NAMES = ("index.html", "futures.html")
FRONTEND_PORT = 18765
INTERACTION_PORT = 18766
PERF_REPETITIONS = 5
PIXEL_DIFF_LIMIT_PCT = 2.0
MEANINGFUL_REGRESSION_LIMIT = 1.10
MIN_ASSET_REQUEST_REDUCTION = 6

CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "manifest-src 'self'; "
    "worker-src 'self'; "
    "base-uri 'self'; "
    "frame-ancestors 'none'"
)


class CanaryFailure(AssertionError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CanaryFailure(message)


class CanaryHandler(SimpleHTTPRequestHandler):
    """Local-only static server with the production CSP and deterministic gzip."""

    server_version = "td18-canary/1.0"

    def log_message(self, format: str, *args) -> None:
        return

    def end_headers(self) -> None:
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        super().end_headers()

    def do_GET(self) -> None:
        path = Path(self.translate_path(self.path))
        if not path.is_file():
            self.send_error(404, "File not found")
            return
        raw = path.read_bytes()
        compress = path.suffix.lower() in {".js", ".css"}
        body = gzip.compress(raw, compresslevel=9, mtime=0) if compress else raw
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(str(path))[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        if compress:
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Vary", "Accept-Encoding")
        self.end_headers()
        self.wfile.write(body)


@contextmanager
def static_server(root: Path, port: int):
    handler = partial(CanaryHandler, directory=str(root))
    httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def run_builder(output_dir: Path) -> dict:
    result = subprocess.run(
        ["node", str(BUILDER), "--out", str(output_dir)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    require(result.returncode == 0, "shadow builder failed: " + result.stderr.strip())
    return json.loads(result.stdout)


def copy_static_assets(target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT / "assets", target / "assets")
    for relative in (
        "split-01.css",
        "split-02.css",
        "split-03.css",
        "split-04.css",
        "split-05.css",
        "split-06.css",
        "split-07.css",
        "styles.css",
        "app.js",
        "pwa.js",
        "manifest.webmanifest",
    ):
        source = ROOT / relative
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    shutil.copytree(ROOT / "js", target / "js")


def parse_bundle_dir() -> Path | None:
    if "--bundle-dir" not in sys.argv:
        return None
    index = sys.argv.index("--bundle-dir")
    if index + 1 >= len(sys.argv):
        raise CanaryFailure("usage: python regression/td18_canary.py [--bundle-dir <directory>]")
    bundle_dir = Path(sys.argv[index + 1]).resolve()
    if not bundle_dir.is_dir():
        raise CanaryFailure(f"bundle directory does not exist: {bundle_dir}")
    return bundle_dir


def prepare_canary_tree(root: Path, bundle_dir: Path | None = None) -> dict[str, Path]:
    classic = root / "classic"
    shadow = root / "shadow"
    copy_static_assets(classic)
    copy_static_assets(shadow)
    shutil.copyfile(ROOT / "service-worker.js", root / "service-worker.js")

    lock = json.loads(LOCKFILE.read_text(encoding="utf-8"))
    classic_inputs = [
        relative
        for bundle in lock["bundles"]
        if bundle["name"] != "derivatives-status-addon"
        for relative in bundle["inputs"]
    ]

    for page_file in PAGE_NAMES:
        original = (ROOT / page_file).read_text(encoding="utf-8-sig")
        script_tags = list(
            re.finditer(
                r'<script\b[^>]*src="[^"]+"[^>]*>\s*</script>',
                original,
                flags=re.IGNORECASE,
            )
        )
        require(script_tags, f"{page_file} has no script tags to replace")
        classic_sources = list(classic_inputs)
        if page_file == "derivatives-status.html":
            classic_sources.extend(
                bundle["inputs"]
                for bundle in lock["bundles"]
                if bundle["name"] == "derivatives-status-addon"
            )
            classic_sources = [item for group in classic_sources for item in (group if isinstance(group, list) else [group])]
        classic_replacement = "".join(f'<script src="{source}"></script>\n' for source in classic_sources)
        classic_html = original[: script_tags[0].start()] + classic_replacement + original[script_tags[-1].end() :]
        (classic / page_file).write_text(classic_html, encoding="utf-8", newline="")

    if bundle_dir is None:
        build_result = run_builder(shadow)
        bundle_names = {
            "common": "common-runtime.js",
            "route": "route-bundle.js",
            "status": "derivatives-status-addon.js",
        }
    else:
        manifest_path = bundle_dir / "manifest.json"
        require(manifest_path.is_file(), f"minify manifest missing: {manifest_path}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        expected = {item["name"]: item for item in manifest.get("bundles", [])}
        bundle_names = {
            "common": expected.get("common-runtime", {}).get("output", ""),
            "route": expected.get("route-bundle", {}).get("output", ""),
            "status": expected.get("derivatives-status-addon", {}).get("output", ""),
        }
        for name in bundle_names.values():
            require(name and (bundle_dir / name).is_file(), f"bundle missing from manifest directory: {name}")
        for name in bundle_names.values():
            shutil.copyfile(bundle_dir / name, shadow / name)
        build_result = {"output": str(bundle_dir), "manifest": "manifest.json", "bundles": manifest["bundles"]}
    for page_file in PAGE_NAMES:
        original = (ROOT / page_file).read_text(encoding="utf-8-sig")
        script_tags = list(
            re.finditer(
                r'<script\b[^>]*src="[^"]+"[^>]*>\s*</script>',
                original,
                flags=re.IGNORECASE,
            )
        )
        require(script_tags, f"{page_file} has no script tags to replace")
        replacement = (
            f'<script src="{bundle_names["common"]}"></script>\n'
            f'<script src="{bundle_names["route"]}"></script>\n'
        )
        if page_file == "derivatives-status.html":
            replacement += f'<script src="{bundle_names["status"]}"></script>\n'
        shadow_html = original[: script_tags[0].start()] + replacement + original[script_tags[-1].end() :]
        (shadow / page_file).write_text(shadow_html, encoding="utf-8", newline="")
    return {"classic": classic, "shadow": shadow, "build": build_result}


def local_request(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.hostname == "127.0.0.1" and parsed.port in {FRONTEND_PORT, INTERACTION_PORT}


def attach_telemetry(page):
    state = {
        "console_errors": [],
        "external_errors": [],
        "page_errors": [],
        "local_request_failures": [],
        "local_http_failures": [],
    }

    def on_console(message) -> None:
        if message.type != "error":
            return
        if _is_external_resource_error(message.text):
            state["external_errors"].append(message.text)
        elif not _is_expected_background_error(message.text):
            state["console_errors"].append(message.text)

    page.on("console", on_console)
    page.on("pageerror", lambda error: state["page_errors"].append(str(error)))
    page.on(
        "requestfailed",
        lambda request: state["local_request_failures"].append(request.url)
        if local_request(request.url) and "/api/" not in request.url
        else None,
    )
    page.on(
        "response",
        lambda response: state["local_http_failures"].append(f"{response.url}={response.status}")
        if local_request(response.url) and "/api/" not in response.url and response.status >= 400
        else None,
    )
    return state


def wait_page_ready(page) -> None:
    try:
        page.wait_for_load_state("load", timeout=30000)
    except Exception:
        pass
    try:
        page.wait_for_load_state("networkidle", timeout=30000)
    except Exception:
        pass
    _wait_dom_stable(page, None)
    page.wait_for_timeout(300)


def page_metrics(page, started: float) -> dict:
    meaningful_ms = None
    deadline = time.perf_counter() + 45
    while time.perf_counter() < deadline:
        try:
            meaningful = page.evaluate(
                "() => { const main = document.querySelector('main, [role=\"main\"], #app, body');"
                " return !!main && (main.innerText || '').trim().length >= 120; }"
            )
            if meaningful:
                meaningful_ms = round((time.perf_counter() - started) * 1000, 1)
                break
        except Exception:
            pass
        page.wait_for_timeout(100)
    raw = page.evaluate(
        """() => {
            const nav = performance.getEntriesByType("navigation")[0] || {};
            const resources = performance.getEntriesByType("resource").map((entry) => ({
                name: entry.name,
                transferSize: entry.transferSize || 0,
                encodedBodySize: entry.encodedBodySize || 0
            }));
            return {
                navigation_ms: nav.duration || 0,
                resources
            };
        }"""
    )
    local_assets = [
        item
        for item in raw["resources"]
        if local_request(item["name"])
        and any(
            marker in urlparse(item["name"]).path
            for marker in (
                "/js/",
                "/split-",
                "/styles.css",
                "/pwa.js",
                "/app.js",
                "/common-runtime.js",
                "/route-bundle.js",
                "/common-runtime.min.js",
                "/route-bundle.min.js",
            )
        )
    ]
    return {
        "navigation_ms": round(raw["navigation_ms"], 1),
        "first_meaningful_render_proxy_ms": meaningful_ms,
        "asset_request_count": len(local_assets),
        "asset_transfer_bytes": sum(item["transferSize"] for item in local_assets),
        "asset_encoded_bytes": sum(item["encodedBodySize"] for item in local_assets),
    }


def navigate(page, url: str) -> dict:
    started = time.perf_counter()
    page.goto(url, wait_until="commit", timeout=30000)
    wait_page_ready(page)
    metrics = page_metrics(page, started)
    metrics["screenshot"] = page.screenshot(full_page=True)
    metrics["counts"] = _measure_page(page)
    return metrics


def make_context(browser, har_path: Path, page_file: str):
    context = browser.new_context(service_workers="block")
    context.route_from_har(str(har_path), url="**/api/**", not_found="abort")
    context.route("**/api/**", lambda route: _background_route_handler(route, page_file))
    return context


def run_visual_and_perf(browser, base_url: str, variant_dir: Path, page_file: str) -> dict:
    har_path = FRONTEND_HAR_DIR / f"{page_file}.har"
    require(har_path.exists(), f"missing frontend HAR: {har_path}")
    context = make_context(browser, har_path, page_file)
    page = context.new_page()
    telemetry = attach_telemetry(page)
    visual = navigate(page, f"{base_url}/{variant_dir.name}/{page_file}")
    context.close()

    cold = []
    warm = []
    for _ in range(PERF_REPETITIONS):
        cold_context = make_context(browser, har_path, page_file)
        cold_page = cold_context.new_page()
        cold_telemetry = attach_telemetry(cold_page)
        cold.append(navigate(cold_page, f"{base_url}/{variant_dir.name}/{page_file}"))
        cold_context.close()

        warm_context = make_context(browser, har_path, page_file)
        warm_page = warm_context.new_page()
        warm_telemetry = attach_telemetry(warm_page)
        warm_page.goto(f"{base_url}/{variant_dir.name}/{page_file}", wait_until="commit", timeout=30000)
        wait_page_ready(warm_page)
        started = time.perf_counter()
        warm_page.reload(wait_until="commit", timeout=30000)
        wait_page_ready(warm_page)
        warm.append(page_metrics(warm_page, started))
        warm_context.close()

        for sample in (cold_telemetry, warm_telemetry):
            telemetry["console_errors"].extend(sample["console_errors"])
            telemetry["external_errors"].extend(sample["external_errors"])
            telemetry["page_errors"].extend(sample["page_errors"])
            telemetry["local_request_failures"].extend(sample["local_request_failures"])
            telemetry["local_http_failures"].extend(sample["local_http_failures"])

    return {
        "visual": visual,
        "telemetry": telemetry,
        "cold": cold,
        "warm": warm,
    }


def p50(rows: list[dict], key: str) -> float:
    values = [row[key] for row in rows if row[key] is not None]
    require(len(values) == PERF_REPETITIONS, f"missing {key} samples: {len(values)}/{PERF_REPETITIONS}")
    return round(float(statistics.median(values)), 1)


def run_interaction(browser, base_url: str, variant_dir: Path, spec) -> dict:
    har_path = INTERACTION_HAR_DIR / f"{spec.file}.har"
    require(har_path.exists(), f"missing interaction HAR: {har_path}")
    context = make_context(browser, har_path, spec.file)
    page = context.new_page()
    telemetry = attach_telemetry(page)
    page.goto(f"{base_url}/{variant_dir.name}/{spec.file}", wait_until="load", timeout=30000)
    wait_page_ready(page)
    requests_seen: list[str] = []
    page.on("request", lambda request: requests_seen.append(request.url) if "/api/" in request.url else None)
    outcomes = [
        run_render_only_step(page, step) if step.action is None else run_step(page, step, requests_seen)
        for step in spec.steps
    ]
    context.close()
    return {"outcomes": outcomes, "telemetry": telemetry}


def summarize_sample(result: dict) -> dict:
    return {
        "cold_p50_meaningful_ms": p50(result["cold"], "first_meaningful_render_proxy_ms"),
        "warm_p50_meaningful_ms": p50(result["warm"], "first_meaningful_render_proxy_ms"),
        "cold_p50_asset_requests": p50(result["cold"], "asset_request_count"),
        "warm_p50_asset_requests": p50(result["warm"], "asset_request_count"),
        "cold_p50_asset_transfer_bytes": p50(result["cold"], "asset_transfer_bytes"),
        "warm_p50_asset_transfer_bytes": p50(result["warm"], "asset_transfer_bytes"),
    }


def compare_page(page_file: str, classic: dict, shadow: dict, spec, interaction: dict, baseline: dict) -> dict:
    failures = []
    classic_visual = classic["visual"]
    shadow_visual = shadow["visual"]
    shadow_telemetry = shadow["telemetry"]
    diff_pct = _pixel_diff_pct(
        (BASELINE_DIR / baseline["screenshot"]).read_bytes(),
        shadow_visual["screenshot"],
    )
    if diff_pct > PIXEL_DIFF_LIMIT_PCT:
        failures.append(f"pixel diff {diff_pct:.2f}% > {PIXEL_DIFF_LIMIT_PCT}%")
    if shadow_visual["counts"] != baseline["counts"]:
        failures.append(f"DOM counts changed: baseline={baseline['counts']} shadow={shadow_visual['counts']}")
    for key in ("console_errors", "page_errors", "local_request_failures", "local_http_failures"):
        if shadow_telemetry[key]:
            failures.append(f"{key}={shadow_telemetry[key][:3]}")
    if shadow_telemetry["external_errors"]:
        failures.append(f"external resource errors require rerun: {shadow_telemetry['external_errors'][:3]}")

    classic_perf = summarize_sample(classic)
    shadow_perf = summarize_sample(shadow)
    for mode in ("cold", "warm"):
        meaningful_key = f"{mode}_p50_meaningful_ms"
        if shadow_perf[meaningful_key] > classic_perf[meaningful_key] * MEANINGFUL_REGRESSION_LIMIT:
            failures.append(
                f"{mode} meaningful p50 {shadow_perf[meaningful_key]}ms > "
                f"classic {classic_perf[meaningful_key]}ms * {MEANINGFUL_REGRESSION_LIMIT}"
            )
        if shadow_perf[f"{mode}_p50_asset_requests"] > classic_perf[f"{mode}_p50_asset_requests"]:
            failures.append(f"{mode} asset request count increased")
        if shadow_perf[f"{mode}_p50_asset_transfer_bytes"] > classic_perf[f"{mode}_p50_asset_transfer_bytes"]:
            failures.append(f"{mode} asset transfer bytes increased")
        if (
            shadow_perf[f"{mode}_p50_asset_requests"]
            > classic_perf[f"{mode}_p50_asset_requests"] - MIN_ASSET_REQUEST_REDUCTION
        ):
            failures.append(f"{mode} asset request reduction is below {MIN_ASSET_REQUEST_REDUCTION}")

    step_failures = [
        f"{outcome['id']}: {outcome['failures']}"
        for outcome in interaction["outcomes"]
        if not outcome["ok"]
    ]
    if step_failures:
        failures.extend(step_failures)
    for key in ("console_errors", "page_errors", "local_request_failures", "local_http_failures"):
        if interaction["telemetry"][key]:
            failures.append(f"interaction {key}={interaction['telemetry'][key][:3]}")

    return {
        "page": page_file,
        "ok": not failures,
        "failures": failures,
        "pixel_diff_pct": round(diff_pct, 3),
        "classic_dom_counts": classic_visual["counts"],
        "shadow_dom_counts": shadow_visual["counts"],
        "classic_perf": classic_perf,
        "shadow_perf": shadow_perf,
        "interaction_steps": len(interaction["outcomes"]),
        "interaction_ok": not step_failures,
        "classic_external_errors": len(classic["telemetry"]["external_errors"]),
        "shadow_external_errors": len(shadow_telemetry["external_errors"]),
    }


def main() -> None:
    baseline = json.loads(FRONTEND_MANIFEST.read_text(encoding="utf-8"))
    baseline_by_file = {item["file"]: item for item in baseline["pages"]}
    with tempfile.TemporaryDirectory(prefix="td18_h10_03_", dir=ROOT / ".tmp") as temp_dir:
        tree = prepare_canary_tree(Path(temp_dir), parse_bundle_dir())
        results = {}
        with static_server(Path(temp_dir), FRONTEND_PORT) as frontend_url:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                try:
                    classic_results = {}
                    shadow_results = {}
                    interactions = {}
                    for page_file in PAGE_NAMES:
                        print(f"[canary] {page_file}: classic visual/perf", flush=True)
                        classic_results[page_file] = run_visual_and_perf(
                            browser, frontend_url, tree["classic"], page_file
                        )
                        print(f"[canary] {page_file}: shadow visual/perf", flush=True)
                        shadow_results[page_file] = run_visual_and_perf(
                            browser, frontend_url, tree["shadow"], page_file
                        )

                        spec = next(spec for spec in CANARY_PAGES if spec.file == page_file)
                        with static_server(Path(temp_dir), INTERACTION_PORT) as interaction_url:
                            print(f"[canary] {page_file}: shadow interaction", flush=True)
                            interactions[page_file] = run_interaction(
                                browser, interaction_url, tree["shadow"], spec
                            )
                        result = compare_page(
                            page_file,
                            classic_results[page_file],
                            shadow_results[page_file],
                            spec,
                            interactions[page_file],
                            baseline_by_file[page_file],
                        )
                        results[page_file] = result
                        print(json.dumps(result, ensure_ascii=False, sort_keys=True), flush=True)
                        require(result["ok"], f"{page_file} canary failed: {result['failures']}")
                finally:
                    browser.close()

    output = {"status": "H10_03_CANARY_OK" if all(item["ok"] for item in results.values()) else "H10_03_CANARY_FAILED", "pages": results}
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    if output["status"] != "H10_03_CANARY_OK":
        raise SystemExit(1)


if __name__ == "__main__":
    try:
        main()
    except (OSError, CanaryFailure, subprocess.SubprocessError) as error:
        print(f"H10_03_CANARY_FAILED: {error}", file=sys.stderr)
        raise SystemExit(1) from error
