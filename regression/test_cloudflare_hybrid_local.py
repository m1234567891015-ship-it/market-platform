"""Local-only integration gate for the Cloudflare hybrid migration."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "regression"))

from market_config import PAGE_ROUTES
from server_harness import find_free_port, start_server


def cleanup_project_workerd() -> None:
    if os.name != "nt":
        return
    project_workerd_pattern = str(REPO_ROOT / "node_modules" / "@cloudflare" / "workerd-*").replace("'", "''")
    subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-Command",
            f"Get-Process -Name workerd -ErrorAction SilentlyContinue | Where-Object {{ $_.Path -like '{project_workerd_pattern}' }} | Stop-Process -Force -ErrorAction SilentlyContinue",
        ],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def http_request(base_url: str, path: str, method: str = "GET", body: bytes | None = None, headers: dict[str, str] | None = None):
    request = urllib.request.Request(base_url + path, data=body, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, dict(response.headers.items()), response.read()
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers.items()), error.read()


def wait_until_ready(base_url: str, timeout: float = 45.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            status, _headers, _body = http_request(base_url, "/index.html")
            if status in {200, 404, 500}:
                return
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(0.5)
    raise AssertionError(f"Wrangler did not become ready: {base_url}")


class FixtureHandler(BaseHTTPRequestHandler):
    def log_message(self, _format: str, *_args) -> None:
        return

    def _record(self, body: bytes) -> tuple[str, dict[str, list[str]]]:
        parsed = urlsplit(self.path)
        record = {
            "method": self.command,
            "path": parsed.path,
            "query": parse_qs(parsed.query, keep_blank_values=True),
            "body": body.decode("utf-8"),
            "headers": {key.lower(): value for key, value in self.headers.items()},
        }
        self.server.records.append(record)  # type: ignore[attr-defined]
        return parsed.path, record["query"]

    def _send(self, status: int, body: bytes, content_type: str = "application/json") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path, _query = self._record(b"")
        if path == "/api/echo/path":
            self._send(200, json.dumps({"ok": True, "path": path}).encode())
        elif path == "/api/failure/500":
            self._send(500, b'{"backend":"five-hundred"}')
        elif path == "/api/failure/502":
            self._send(502, b'{"backend":"bad-gateway"}')
        elif path == "/api/failure/invalid-json":
            self._send(200, b"{not-json", "application/json")
        elif path == "/api/failure/empty":
            self._send(200, b"", "application/json")
        else:
            self._send(404, b'{"success":false,"error_code":"NOT_FOUND"}')

    def do_POST(self) -> None:
        length = int(self.headers.get("content-length", "0"))
        body = self.rfile.read(length)
        path, query = self._record(body)
        self._send(200, json.dumps({"method": "POST", "path": path, "query": query, "body": body.decode()}).encode())


def start_fixture() -> tuple[ThreadingHTTPServer, str]:
    server = ThreadingHTTPServer(("127.0.0.1", find_free_port()), FixtureHandler)
    server.records = []  # type: ignore[attr-defined]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{server.server_port}"


class WranglerHandle:
    def __init__(self, origin_url: str):
        self.port = find_free_port()
        self.base_url = f"http://127.0.0.1:{self.port}"
        log_path = REPO_ROOT / ".tmp" / "cloudflare-hybrid-wrangler.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log = log_path.open("w", encoding="utf-8")
        node = shutil.which("node") or "node"
        command = [
            node,
            str(REPO_ROOT / "node_modules" / "wrangler" / "bin" / "wrangler.js"),
            "dev",
            "--config",
            "cloudflare/wrangler.jsonc",
            "--local",
            "--port",
            str(self.port),
            "--show-interactive-dev-session=false",
            "--var",
            f"ORIGIN_API_BASE:{origin_url}",
        ]
        self.process = subprocess.Popen(command, cwd=REPO_ROOT, stdout=log, stderr=subprocess.STDOUT, env=os.environ.copy())
        self._log = log
        try:
            wait_until_ready(self.base_url)
        except Exception:
            self.stop()
            raise

    def stop(self) -> None:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(self.process.pid), "/T", "/F"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if self.process.poll() is None:
                self.process.wait(timeout=15)
        elif self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=15)
        if os.name == "nt":
            cleanup_project_workerd()
        self._log.close()


def assert_json(body: bytes) -> dict:
    value = json.loads(body.decode("utf-8"))
    assert isinstance(value, dict), value
    return value


def run_gate() -> dict[str, object]:
    cleanup_project_workerd()
    subprocess.run([sys.executable, "scripts/build-cloudflare-static.py"], cwd=REPO_ROOT, check=True)
    subprocess.run([sys.executable, "scripts/verify-cloudflare-dist.py"], cwd=REPO_ROOT, check=True)

    result: dict[str, object] = {"static_pages": 0, "api_checks": 0, "proxy_checks": 0}
    with start_server(extra_env={"MARKET_PULSE_DISABLE_BACKGROUND": "1"}) as flask:
        edge = WranglerHandle(flask.base_url)
        try:
            for page in sorted({name for name in PAGE_ROUTES.values() if name.endswith(".html")}):
                status, headers, body = http_request(edge.base_url, f"/{page}")
                assert status == 200 and body, (page, status)
            status, _headers, body = http_request(edge.base_url, "/")
            assert status == 200 and body, ("/", status)
            result["static_pages"] = 21

            for path in ("/manifest.webmanifest", "/service-worker.js", "/assets/app-icon.svg", "/split-01.css", "/js/core.js"):
                status, _headers, body = http_request(edge.base_url, path)
                assert status == 200 and body, (path, status)
            sw_body = http_request(edge.base_url, "/service-worker.js")[2].decode("utf-8")
            assert "/api/" in sw_body and "cache" in sw_body.lower(), "service worker API bypass missing"

            for path in ("/api/health", "/api/not-a-real-route?probe=1"):
                direct_status, _direct_headers, direct_body = http_request(flask.base_url, path)
                proxy_status, proxy_headers, proxy_body = http_request(edge.base_url, path)
                assert proxy_status == direct_status, (path, direct_status, proxy_status)
                direct_json = assert_json(direct_body)
                proxy_json = assert_json(proxy_body)
                assert proxy_json.get("success") == direct_json.get("success"), path
                assert proxy_json.get("error_code") == direct_json.get("error_code"), path
                assert proxy_headers.get("Cache-Control", "").startswith("no-store"), path
            result["api_checks"] = 2
        finally:
            edge.stop()

    fixture, fixture_url = start_fixture()
    try:
        edge = WranglerHandle(fixture_url)
        try:
            request_body = b'{"symbol":"2330"}'
            status, _headers, body = http_request(
                edge.base_url,
                "/api/echo/path?z=last&a=first",
                method="POST",
                body=request_body,
                headers={"Accept": "application/json", "Content-Type": "application/json", "X-Forwarded-Host": "evil.invalid"},
            )
            assert status == 200
            echoed = assert_json(body)
            assert echoed["method"] == "POST" and echoed["path"] == "/api/echo/path", echoed
            assert echoed["query"] == {"z": ["last"], "a": ["first"]}, echoed
            assert echoed["body"] == request_body.decode(), echoed
            record = fixture.records[-1]  # type: ignore[attr-defined]
            assert "x-forwarded-host" not in record["headers"], record

            for path, expected_status in (("/api/failure/500", 500), ("/api/failure/502", 502)):
                status, _headers, body = http_request(edge.base_url, path)
                assert status == expected_status and body != b"", (path, status, body)
            for path in ("/api/failure/invalid-json", "/api/failure/empty"):
                status, _headers, body = http_request(edge.base_url, path)
                payload = assert_json(body)
                assert status == 502 and payload.get("success") is False and payload.get("error_code") == "UPSTREAM_INVALID_RESPONSE", (path, status, payload)

            status, _headers, body = http_request(edge.base_url, "/api/echo/path?upstream=http://evil.invalid")
            assert status == 200 and fixture.records[-1]["path"] == "/api/echo/path", fixture.records[-1]  # type: ignore[attr-defined]
            assert assert_json(body)["path"] == "/api/echo/path"
            status, _headers, body = http_request(edge.base_url, "/api/../secret")
            assert status != 200 or b"success" not in body, (status, body)
            result["proxy_checks"] = 7
        finally:
            edge.stop()
    finally:
        fixture.shutdown()
        fixture.server_close()

    unavailable = WranglerHandle(f"http://127.0.0.1:{find_free_port()}")
    try:
        status, _headers, body = http_request(unavailable.base_url, "/api/health")
        payload = assert_json(body)
        assert status == 502 and payload.get("success") is False and payload.get("error_code") == "UPSTREAM_UNAVAILABLE", payload
        result["fail_closed_backend_down"] = True
    finally:
        unavailable.stop()
    return result


if __name__ == "__main__":
    summary = run_gate()
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
