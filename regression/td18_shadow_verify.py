"""TD-18 H-10-02/H-10-04: verify shadow artifacts and production wiring.

The verifier rebuilds the H-10-01 shadow artifacts into a temporary directory,
then checks bundle metadata, classic-script global scope, load-order parity,
escapeHtml uniqueness, effective CSP headers, and local asset availability.
It supports both the original classic HTML entries and the H-10-04 production
bundle entries; it does not edit baselines, CSP, or deployment configuration.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen

REGRESSION_DIR = Path(__file__).resolve().parent
ROOT = REGRESSION_DIR.parent
LOCKFILE = REGRESSION_DIR / "td18_shadow_build.lock.json"
MINIFY_LOCKFILE = REGRESSION_DIR / "td18_minify_build.lock.json"
MINIFY_ASSET_VERSION = "td18-minify-5e25eb24db6b5c9c"
FULL_ESM_MANIFEST = ROOT / "docs" / "TD02_FULL_ESM_build_manifest_2026-09-01.json"
FULL_ESM_ASSET_VERSION = json.loads(FULL_ESM_MANIFEST.read_text(encoding="utf-8"))["version"]
BUILDER = REGRESSION_DIR / "td18_shadow_build.js"
BASELINE_SYMBOLS = REGRESSION_DIR / "baseline" / "frontend" / "global_symbols.json"

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(REGRESSION_DIR))

from security_guardrail_check import js_top_level_declared_names  # noqa: E402
from server_harness import start_server  # noqa: E402


class VerificationFailure(AssertionError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationFailure(message)


class PageAssets(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.scripts: list[str] = []
        self.stylesheets: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.lower(): value for key, value in attrs}
        if tag.lower() == "script" and values.get("src"):
            self.scripts.append(values["src"] or "")
        if tag.lower() == "link" and values.get("href"):
            rel = (values.get("rel") or "").lower().split()
            if "stylesheet" in rel:
                self.stylesheets.append(values["href"] or "")


def load_lock() -> dict:
    require(LOCKFILE.exists(), f"missing H-10-01 lockfile: {LOCKFILE}")
    lock = json.loads(LOCKFILE.read_text(encoding="utf-8"))
    require(lock.get("lockfileVersion") == 1, "unsupported shadow lockfile version")
    require(lock.get("nodeVersion") == "24.18.0", "H-10-01 Node lock is not 24.18.0")
    require(
        lock.get("builder", {}).get("name") == "td18-shadow-concat"
        and lock.get("builder", {}).get("version") == "1.0.0",
        "H-10-01 builder lock mismatch",
    )
    require(len(lock.get("bundles", [])) == 3, "H-10-01 must define three shadow bundles")
    return lock


def build_shadow(output_dir: Path) -> dict:
    result = subprocess.run(
        ["node", str(BUILDER), "--out", str(output_dir)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    require(result.returncode == 0, "shadow builder failed: " + result.stderr.strip())
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise VerificationFailure("shadow builder emitted invalid JSON") from exc


def verify_artifact_metadata(lock: dict, build_result: dict, output_dir: Path) -> dict:
    bundles = build_result.get("bundles", [])
    require(len(bundles) == len(lock["bundles"]), "shadow manifest bundle count mismatch")
    by_name = {item["name"]: item for item in bundles}
    require(len(by_name) == len(bundles), "shadow manifest has duplicate bundle names")
    for locked in lock["bundles"]:
        actual = by_name.get(locked["name"])
        require(actual is not None, f"missing shadow bundle: {locked['name']}")
        require(actual["output"] == locked["output"], f"{locked['name']} output name drifted")
        require(actual["sourceMap"] == locked["sourceMap"], f"{locked['name']} source map name drifted")
        require(
            [item["path"] for item in actual["inputs"]] == locked["inputs"],
            f"{locked['name']} input order drifted",
        )
        output_path = output_dir / actual["output"]
        map_path = output_dir / actual["sourceMap"]
        require(output_path.is_file(), f"missing shadow artifact: {output_path}")
        require(map_path.is_file(), f"missing shadow source map: {map_path}")
        source_map = json.loads(map_path.read_text(encoding="utf-8"))
        require(source_map.get("version") == 3, f"{locked['name']} source map is not v3")
        require(source_map.get("sources") == locked["inputs"], f"{locked['name']} source map sources drifted")
        syntax = subprocess.run(
            ["node", "--check", str(output_path)],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        require(syntax.returncode == 0, f"{locked['name']} shadow artifact failed node --check: {syntax.stderr}")
    return by_name


def verify_global_scope(lock: dict, output_dir: Path) -> dict:
    baseline = set(json.loads(BASELINE_SYMBOLS.read_text(encoding="utf-8")))
    source_files = [
        relative
        for bundle in lock["bundles"]
        for relative in bundle["inputs"]
        if relative.startswith("js/") or relative == "app.js"
    ]
    current_sources: set[str] = set()
    for relative in source_files:
        current_sources |= js_top_level_declared_names((ROOT / relative).read_text(encoding="utf-8-sig"))

    shadow_names: set[str] = set()
    for bundle_name in ("common-runtime", "route-bundle"):
        shadow_path = output_dir / next(
            bundle["output"] for bundle in lock["bundles"] if bundle["name"] == bundle_name
        )
        shadow_names |= js_top_level_declared_names(shadow_path.read_text(encoding="utf-8-sig"))

    require(current_sources == baseline, "current classic sources do not match 895-symbol baseline")
    require(shadow_names == baseline, "shadow common runtime + route bundle changed global symbol set")
    return {"baseline_symbols": len(baseline), "shadow_symbols": len(shadow_names)}


def verify_escapehtml(lock: dict, output_dir: Path) -> dict:
    common = next(bundle for bundle in lock["bundles"] if bundle["name"] == "common-runtime")
    route = next(bundle for bundle in lock["bundles"] if bundle["name"] == "route-bundle")
    source = "\n".join(
        (output_dir / name).read_text(encoding="utf-8-sig")
        for name in (common["output"], route["output"])
    )
    count = source.count("function escapeHtml(")
    require(count == 1, f"shadow common + route bundle must define escapeHtml once, found {count}")
    require("function escapeHtml(" in (output_dir / common["output"]).read_text(encoding="utf-8-sig"), "escapeHtml moved out of common runtime")
    return {"escapeHtml_definitions": count, "location": "common-runtime.js"}


def page_assets() -> dict[str, PageAssets]:
    result = {}
    for html_file in sorted(ROOT.glob("*.html")):
        parser = PageAssets()
        parser.feed(html_file.read_text(encoding="utf-8-sig"))
        result[html_file.name] = parser
    require(len(result) == 21, f"expected 21 HTML pages, found {len(result)}")
    return result


def normalized_local(value: str) -> str | None:
    parsed = urlparse(value)
    if parsed.scheme or parsed.netloc or value.startswith("//"):
        return None
    path = unquote(parsed.path).lstrip("/")
    require(".." not in Path(path).parts, f"local asset path escapes root: {value}")
    return path


def verify_load_order_and_files(lock: dict, pages: dict[str, PageAssets]) -> dict:
    uses_full_esm = any(
        normalized_local(value) == "market-pulse-esm-loader.js"
        for parser in pages.values()
        for value in parser.scripts
    )
    if uses_full_esm:
        for page_name, parser in pages.items():
            scripts = [normalized_local(value) for value in parser.scripts]
            scripts = [value for value in scripts if value is not None]
            require(
                scripts == ["market-pulse-esm-loader.js"],
                f"{page_name} full ESM script order differs from locked loader wiring",
            )
        require((ROOT / "market-pulse-esm-loader.js").is_file(), "missing full ESM loader")
        require((ROOT / "market-pulse-esm.min.js").is_file(), "missing full ESM production asset")
        require((ROOT / "market-pulse-esm.min.js.map").is_file(), "missing full ESM source map")
        local_asset_paths = {"market-pulse-esm-loader.js", "market-pulse-esm.min.js", "market-pulse-esm.min.js.map"}
        for parser in pages.values():
            for value in parser.scripts + parser.stylesheets:
                relative = normalized_local(value)
                if relative is not None:
                    local_asset_paths.add(relative)
                    require((ROOT / relative).is_file(), f"page references missing local asset: {value}")
        return {
            "pages": len(pages),
            "modes": ["production-full-esm"],
            "base_script_order": ["market-pulse-esm-loader.js"],
            "local_asset_files": sorted(local_asset_paths),
        }

    wiring_lock = lock
    uses_minified = any(
        normalized_local(value) in {"common-runtime.min.js", "route-bundle.min.js"}
        for parser in pages.values()
        for value in parser.scripts
    )
    if uses_minified:
        wiring_lock = json.loads(MINIFY_LOCKFILE.read_text(encoding="utf-8"))
    expected_base = [
        relative
        for bundle in wiring_lock["bundles"]
        if bundle["name"] != "derivatives-status-addon"
        for relative in bundle["inputs"]
    ]
    expected_status = expected_base + [
        relative
        for bundle in wiring_lock["bundles"]
        if bundle["name"] == "derivatives-status-addon"
        for relative in bundle["inputs"]
    ]
    expected_bundle = [
        bundle["output"]
        for bundle in wiring_lock["bundles"]
        if bundle["name"] != "derivatives-status-addon"
    ]
    expected_bundle_status = expected_bundle + [
        bundle["output"]
        for bundle in wiring_lock["bundles"]
        if bundle["name"] == "derivatives-status-addon"
    ]
    local_asset_paths: set[str] = set()
    modes: set[str] = set()
    status_uses_esm_loader = any(
        normalized_local(value) == "derivatives-status-esm-loader.js"
        for value in pages["derivatives-status.html"].scripts
    )
    for page_name, parser in pages.items():
        scripts = [normalized_local(value) for value in parser.scripts]
        scripts = [value for value in scripts if value is not None]
        for raw in parser.scripts:
            normalized = normalized_local(raw)
            if normalized in {"common-runtime.min.js", "route-bundle.min.js", "derivatives-status-addon.min.js"}:
                require(
                    urlparse(raw).query == "v=" + MINIFY_ASSET_VERSION,
                    f"{page_name} minified asset is missing the locked version query: {raw}",
                )
        if any(value in expected_bundle for value in scripts):
            if page_name == "derivatives-status.html" and status_uses_esm_loader:
                expected = expected_bundle + ["derivatives-status-esm-loader.js"]
            else:
                expected = expected_bundle_status if page_name == "derivatives-status.html" else expected_bundle
            modes.add("production-bundle")
        else:
            expected = expected_status if page_name == "derivatives-status.html" else expected_base
            modes.add("classic-fallback")
        require(scripts == expected, f"{page_name} frontend script order differs from locked order")
        for value in parser.scripts + parser.stylesheets:
            relative = normalized_local(value)
            if relative is not None:
                local_asset_paths.add(relative)
                require((ROOT / relative).is_file(), f"{page_name} references missing local asset: {value}")
    production_mode = "production-minified" if uses_minified else "production-bundle"
    if "production-bundle" in modes:
        for bundle in wiring_lock["bundles"]:
            require((ROOT / bundle["output"]).is_file(), f"missing production bundle: {bundle['output']}")
            require((ROOT / bundle["sourceMap"]).is_file(), f"missing production source map: {bundle['sourceMap']}")
        modes.discard("production-bundle")
        modes.add(production_mode)
    return {
        "pages": len(pages),
        "modes": sorted(modes),
        "base_script_order": expected_bundle if production_mode in modes else expected_base,
        "local_asset_files": sorted(local_asset_paths),
    }


def get_local(base_url: str, relative: str) -> tuple[int, str | None, str | None]:
    request = Request(base_url + "/" + relative, headers={"Connection": "close"})
    with urlopen(request, timeout=20) as response:
        return response.status, response.headers.get("Content-Security-Policy"), response.headers.get("Cache-Control")


def verify_effective_headers_and_assets(pages: dict[str, PageAssets], full_esm: bool = False) -> dict:
    local_assets = set()
    for parser in pages.values():
        for value in parser.scripts + parser.stylesheets:
            relative = normalized_local(value)
            if relative is not None:
                local_assets.add(relative)
    if full_esm:
        local_assets.update({"market-pulse-esm.min.js", "market-pulse-esm.min.js.map"})

    with start_server() as server:
        status, csp, _ = get_local(server.base_url, "index.html")
        require(status == 200, f"index.html fallback entry returned HTTP {status}")
        require(csp, "index.html response omitted Content-Security-Policy")
        directives = {
            part.strip().split(None, 1)[0]: part.strip().split()[1:]
            for part in csp.split(";")
            if part.strip()
        }
        require(directives.get("script-src") == ["'self'"], "CSP script-src is not exactly self")
        require("'unsafe-inline'" not in directives["script-src"], "CSP script-src contains unsafe-inline")
        require("'unsafe-eval'" not in directives["script-src"], "CSP script-src contains unsafe-eval")
        require(directives.get("frame-ancestors") == ["'none'"], "CSP frame-ancestors is not none")

        futures_status, _, _ = get_local(server.base_url, "futures.html")
        require(futures_status == 200, f"futures.html fallback entry returned HTTP {futures_status}")
        failures = []
        for relative in sorted(local_assets):
            asset_status, _, _ = get_local(server.base_url, relative)
            if asset_status != 200:
                failures.append(f"{relative}={asset_status}")
        require(not failures, "local asset HTTP failures: " + ", ".join(failures))
        cache_file = "market-pulse-esm.min.js" if full_esm else "common-runtime.min.js"
        cache_version = FULL_ESM_ASSET_VERSION if full_esm else MINIFY_ASSET_VERSION
        cache_status, _, cache_control = get_local(server.base_url, f"{cache_file}?v={cache_version}")
        require(cache_status == 200, f"versioned minified asset returned HTTP {cache_status}")
        require(
            cache_control == "public, max-age=31536000, immutable",
            f"versioned minified asset cache policy drifted: {cache_control!r}",
        )
    expected_cache_version = f"market-pulse-swr-{FULL_ESM_ASSET_VERSION}" if full_esm else "market-pulse-swr-20260901-td18-minify-5e25eb24db6b5c9c"
    require(
        f'CACHE_VERSION = "{expected_cache_version}"' in (ROOT / "service-worker.js").read_text(encoding="utf-8"),
        "Service Worker CACHE_VERSION does not match the active frontend asset set",
    )
    return {
        "csp": "script-src self; frame-ancestors none",
        "local_asset_404": 0,
        "immutable_cache": "public, max-age=31536000, immutable",
        "service_worker_cache_version": expected_cache_version,
    }


def main() -> None:
    lock = load_lock()
    with tempfile.TemporaryDirectory(prefix="td18_h10_02_", dir=ROOT / ".tmp") as temp_dir:
        output_dir = Path(temp_dir)
        build_result = build_shadow(output_dir)
        artifact_summary = verify_artifact_metadata(lock, build_result, output_dir)
        scope_summary = verify_global_scope(lock, output_dir)
        escape_summary = verify_escapehtml(lock, output_dir)
        pages = page_assets()
        order_summary = verify_load_order_and_files(lock, pages)
        header_summary = verify_effective_headers_and_assets(pages, full_esm="production-full-esm" in order_summary["modes"])
    print(
        json.dumps(
            {
                "status": "H10_02_VERIFY_OK",
                "artifacts": sorted(artifact_summary),
                "global_scope": scope_summary,
                "escapeHtml": escape_summary,
                "load_order": order_summary,
                "headers_assets": header_summary,
                "production_wiring": order_summary["modes"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except (OSError, VerificationFailure, subprocess.SubprocessError) as error:
        print(f"H10_02_VERIFY_FAILED: {error}", file=sys.stderr)
        raise SystemExit(1) from error
