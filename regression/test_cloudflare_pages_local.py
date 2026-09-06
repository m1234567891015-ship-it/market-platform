"""Local-only Cloudflare Pages adaptation gate.

The gate uses a disposable Flask database, Wrangler Pages local runtime, and a
fixture origin. It never contacts Pages deployment APIs and never uses the
authoritative SQLite file.
"""
from __future__ import annotations

import json
import http.client
import importlib.util
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "regression"))

from market_config import PAGE_ROUTES
from server_harness import find_free_port, start_server
from test_cloudflare_hybrid_local import (
    FixtureHandler,
    assert_json,
    cleanup_project_workerd,
    start_fixture,
)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BUILD_MODULE = load_module(REPO_ROOT / "scripts" / "build-cloudflare-static.py", "pages_build_cloudflare_static")
VERIFY_MODULE = load_module(REPO_ROOT / "scripts" / "verify-cloudflare-dist.py", "pages_verify_cloudflare_dist")
PAGES_DIST = REPO_ROOT / ".tmp" / "cloudflare-pages-static"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


NO_REDIRECT_OPENER = urllib.request.build_opener(NoRedirect)


def http_request(base_url: str, path: str, method: str = "GET", body: bytes | None = None, headers: dict[str, str] | None = None):
    request = urllib.request.Request(base_url + path, data=body, headers=headers or {}, method=method)
    try:
        with NO_REDIRECT_OPENER.open(request, timeout=30) as response:
            return response.status, dict(response.headers.items()), response.read()
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers.items()), error.read()


def absolute_form_request(base_url: str, target: str, headers: dict[str, str] | None = None):
    parsed = urlsplit(base_url)
    connection = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=30)
    try:
        connection.request("GET", target, headers=headers or {})
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        connection.close()


def wait_until_ready(base_url: str, timeout: float = 45.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            status, _headers, _body = http_request(base_url, "/index.html")
            if status in {200, 301, 302, 303, 307, 308, 404, 500}:
                return
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(0.5)
    raise AssertionError(f"Pages local runtime did not become ready: {base_url}")


class PagesHandle:
    def __init__(self, origin_url: str, directory: Path = PAGES_DIST):
        self.port = find_free_port()
        self.base_url = f"http://127.0.0.1:{self.port}"
        log_path = REPO_ROOT / ".tmp" / "cloudflare-pages-wrangler.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log = log_path.open("w", encoding="utf-8")
        node = shutil.which("node") or "node"
        directory_arg = str(directory.relative_to(REPO_ROOT)).replace("\\", "/")
        command = [
            node,
            str(REPO_ROOT / "node_modules" / "wrangler" / "bin" / "wrangler.js"),
            "pages",
            "dev",
            directory_arg,
            "--ip",
            "127.0.0.1",
            "--port",
            str(self.port),
            "--binding",
            f"ORIGIN_API_BASE={origin_url}",
            "--compatibility-date",
            "2026-09-06",
            "--show-interactive-dev-session=false",
            "--log-level",
            "error",
        ]
        env = os.environ.copy()
        env["WRANGLER_SEND_METRICS"] = "false"
        env["XDG_CONFIG_HOME"] = str(REPO_ROOT / ".tmp" / "wrangler-pages-config")
        self.process = subprocess.Popen(command, cwd=REPO_ROOT, stdout=self._log, stderr=subprocess.STDOUT, env=env)
        try:
            wait_until_ready(self.base_url)
        except Exception:
            self.stop()
            raise

    def stop(self) -> None:
        if self.process.poll() is None:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(self.process.pid), "/T", "/F"],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                self.process.terminate()
            try:
                self.process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=15)
        cleanup_project_workerd()
        self._log.close()


def required_headers(headers: dict[str, str], *, api: bool) -> None:
    lowered = {key.lower(): value for key, value in headers.items()}
    for name, expected in {
        "x-content-type-options": "nosniff",
        "x-frame-options": "DENY",
        "referrer-policy": "strict-origin-when-cross-origin",
        "permissions-policy": "camera=(), microphone=(), geolocation=()",
        "content-security-policy": "frame-ancestors 'none'",
        "strict-transport-security": "max-age=31536000",
    }.items():
        assert expected in lowered.get(name, ""), (name, lowered.get(name))
    if api:
        assert lowered.get("cache-control", "").startswith("no-store"), lowered


def compare_worker_and_pages(fixture, fixture_url: str) -> dict[str, object]:
    worker_command = [
        shutil.which("node") or "node",
        str(REPO_ROOT / "node_modules" / "wrangler" / "bin" / "wrangler.js"),
        "dev",
        "--config",
        "cloudflare/wrangler.jsonc",
        "--local",
        "--port",
        str(find_free_port()),
        "--show-interactive-dev-session=false",
        "--var",
        f"ORIGIN_API_BASE:{fixture_url}",
        "--log-level",
        "error",
    ]
    log_path = REPO_ROOT / ".tmp" / "cloudflare-pages-worker-parity.log"
    log = log_path.open("w", encoding="utf-8")
    worker_env = os.environ.copy()
    worker_env["WRANGLER_SEND_METRICS"] = "false"
    worker_env["XDG_CONFIG_HOME"] = str(REPO_ROOT / ".tmp" / "wrangler-pages-config")
    worker_process = subprocess.Popen(worker_command, cwd=REPO_ROOT, stdout=log, stderr=subprocess.STDOUT, env=worker_env)
    worker_url = f"http://127.0.0.1:{worker_command[worker_command.index('--port') + 1]}"
    pages = None
    try:
        wait_until_ready(worker_url)
        pages = PagesHandle(fixture_url)
        cases = [
            ("GET", "/api/echo/path?z=last&a=first", None, {"Accept": "application/json", "X-Forwarded-Host": "evil.invalid"}),
            ("POST", "/api/echo/path?z=last&a=first", b'{"symbol":"2330"}', {"Content-Type": "application/json", "Forwarded": "host=evil.invalid"}),
            ("GET", "/api/failure/500", None, {}),
            ("GET", "/api/failure/502", None, {}),
            ("GET", "/api/failure/invalid-json", None, {}),
            ("GET", "/api/failure/empty", None, {}),
            ("GET", "/api/echo/path?upstream=http://evil.invalid", None, {}),
        ]
        static_status, _static_headers, static_body = http_request(pages.base_url, "/index.html")
        assert static_status in {200, 301, 302, 303, 307, 308} and static_body is not None
        assert not fixture.records, fixture.records  # type: ignore[attr-defined]
        compared = 0
        for method, path, body, headers in cases:
            worker_result = http_request(worker_url, path, method=method, body=body, headers=headers)
            pages_result = http_request(pages.base_url, path, method=method, body=body, headers=headers)
            assert worker_result[0] == pages_result[0], (path, worker_result[0], pages_result[0])
            assert worker_result[2] == pages_result[2], (path, worker_result[2], pages_result[2])
            for header in ("Content-Type", "Cache-Control", "Content-Security-Policy", "X-Content-Type-Options"):
                assert worker_result[1].get(header) == pages_result[1].get(header), (path, header)
            compared += 1
        absolute_target = "http://evil.invalid/api/echo/path?absolute=1"
        worker_result = absolute_form_request(worker_url, absolute_target)
        pages_result = absolute_form_request(pages.base_url, absolute_target)
        assert worker_result[0] == pages_result[0] and worker_result[0] in {400, 404, 500, 502}, (worker_result[0], pages_result[0], worker_result[2], pages_result[2])
        assert worker_result[2] == pages_result[2], (worker_result[2], pages_result[2])
        compared += 1
        records = fixture.records  # type: ignore[attr-defined]
        assert len(records) == len(cases) * 2, records
        expected_host = urlsplit(fixture_url).netloc
        assert all(record["headers"].get("host") == expected_host for record in records), records
        return {"cases": compared, "passed": True, "static_function_free": True, "fixture_records_checked": True}
    finally:
        if pages:
            pages.stop()
        if worker_process.poll() is None:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(worker_process.pid), "/T", "/F"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                worker_process.terminate()
            try:
                worker_process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                worker_process.kill()
                worker_process.wait(timeout=15)
        cleanup_project_workerd()
        log.close()


def run_gate() -> dict[str, object]:
    cleanup_project_workerd()
    if PAGES_DIST.exists():
        shutil.rmtree(PAGES_DIST)
    BUILD_MODULE.build_dist(PAGES_DIST)
    verify_summary = VERIFY_MODULE.verify_dist(PAGES_DIST)
    assert verify_summary["ok"] is True, verify_summary
    assert verify_summary["pages_routes"] == {"version": 1, "include": ["/api/*"], "exclude": []}, verify_summary

    pages = None
    result: dict[str, object] = {"pages_routes": verify_summary["pages_routes"]}
    with start_server(extra_env={"MARKET_PULSE_DISABLE_BACKGROUND": "1"}) as flask:
        direct_status, _direct_headers, _direct_body = http_request(flask.base_url, "/api/health")
        assert direct_status == 200, direct_status
        result["flask_port"] = int(flask.base_url.rsplit(":", 1)[1])
        pages = PagesHandle(flask.base_url)
        result["pages_port"] = pages.port
        result["pages_url"] = pages.base_url
        result["pages_startup"] = True
        try:
            page_names = sorted({name for name in PAGE_ROUTES.values() if name.endswith(".html")})
            redirect_count = 0
            for page in page_names:
                status, headers, body = http_request(pages.base_url, f"/{page}")
                required_headers(headers, api=False)
                if status in {301, 302, 303, 307, 308}:
                    redirect_count += 1
                    location = headers.get("Location")
                    assert location, (page, status, headers)
                    status, headers, body = http_request(pages.base_url, location)
                assert status == 200 and body, (page, status)
                required_headers(headers, api=False)
            result["static_pages"] = len(page_names)
            result["static_redirects"] = redirect_count

            canonical_status, canonical_headers, canonical_body = http_request(pages.base_url, "/derivatives-analytics.html")
            required_headers(canonical_headers, api=False)
            canonical_location = None
            if canonical_status in {301, 302, 303, 307, 308}:
                canonical_location = canonical_headers.get("Location")
                assert canonical_location == "/derivatives-analytics", (canonical_status, canonical_location)
                canonical_final_status, canonical_final_headers, canonical_final_body = http_request(pages.base_url, canonical_location)
                assert canonical_final_status == 200 and canonical_final_body, canonical_final_status
                required_headers(canonical_final_headers, api=False)
            else:
                assert canonical_status == 200 and canonical_body, canonical_status
            extensionless_status, extensionless_headers, extensionless_body = http_request(pages.base_url, "/derivatives-analytics")
            if extensionless_status in {301, 302, 303, 307, 308}:
                location = extensionless_headers.get("Location")
                assert location, extensionless_headers
                final_status, _final_headers, final_body = http_request(pages.base_url, location)
                assert final_status == 200 and final_body, (location, final_status)
                result["html_canonicalization"] = {"direct_html": canonical_status, "direct_location": canonical_location, "extensionless": extensionless_status, "location": location, "final": final_status}
            else:
                assert extensionless_status == 200 and extensionless_body, extensionless_status
                result["html_canonicalization"] = {"direct_html": canonical_status, "direct_location": canonical_location, "extensionless": extensionless_status, "location": None, "final": extensionless_status}

            for path in ("/manifest.webmanifest", "/service-worker.js"):
                status, _headers, body = http_request(pages.base_url, path)
                assert status == 200 and body, (path, status)
            sw_body = http_request(pages.base_url, "/service-worker.js")[2].decode("utf-8")
            assert "self.addEventListener(\"fetch\"" in sw_body
            assert "url.pathname.startsWith(\"/api/\")" in sw_body and "return false" in sw_body
            api_headers = http_request(pages.base_url, "/api/health")[1]
            required_headers(api_headers, api=True)
            result["service_worker"] = True
            result["static_headers"] = True
            result["api_security_headers"] = True

            api_paths = (
                "/api/health",
                "/api/futures?limit=12",
                "/api/options?limit=12",
                "/api/options/chain?underlying=TXO&source=auto",
                "/api/pcr?underlying=TXO&source=auto",
                "/api/institution?product=TX",
                "/api/basis?future=TX&spot=TAIEX",
            )
            api_states = {}
            for path in api_paths:
                status, headers, body = http_request(pages.base_url, path)
                assert status in {200, 502, 503, 504}, (path, status, body[:200])
                assert_json(body)
                required_headers(headers, api=True)
                api_states[path] = "PASS" if status == 200 else "FAIL_CLOSED"
            result["api_states"] = api_states
        finally:
            pages.stop()

        unavailable = PagesHandle(f"http://127.0.0.1:{find_free_port()}")
        try:
            status, _headers, body = http_request(unavailable.base_url, "/api/health")
            payload = assert_json(body)
            assert status == 502 and payload.get("success") is False and payload.get("error_code") == "UPSTREAM_UNAVAILABLE", payload
            result["fail_closed"] = True
        finally:
            unavailable.stop()

    fixture, fixture_url = start_fixture()
    try:
        parity = compare_worker_and_pages(fixture, fixture_url)
        result["worker_pages_parity"] = parity
        assert parity["passed"] is True
        assert all(record["path"].startswith("/api/") for record in fixture.records), fixture.records  # type: ignore[attr-defined]
        assert all(not any(name in record["headers"] for name in ("forwarded", "x-forwarded-host", "x-forwarded-for")) for record in fixture.records), fixture.records  # type: ignore[attr-defined]
        result["open_proxy_risk"] = False
        result["path_normalization"] = True
    finally:
        fixture.shutdown()
        fixture.server_close()

    return result


if __name__ == "__main__":
    print(json.dumps(run_gate(), ensure_ascii=False, sort_keys=True))
