"""TD-03 HTTP canary with two independent app.py worker processes.

Gunicorn is not available on Windows because it requires ``fcntl``. This
runner provides the equivalent process-isolation evidence with two Flask
worker processes, each using its own temporary SQLite/cache paths while both
use the same isolated Redis namespace. It never touches production data.
"""
from __future__ import annotations

import http.client
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_health(port: int) -> None:
    deadline = time.time() + 45
    while time.time() < deadline:
        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
            conn.request("GET", "/api/health")
            response = conn.getresponse()
            response.read()
            conn.close()
            if response.status == 200:
                return
        except (ConnectionError, OSError, http.client.HTTPException):
            pass
        time.sleep(0.25)
    raise RuntimeError(f"worker on port {port} did not become healthy")


def get_json(port: int, path: str) -> tuple[int, dict]:
    request = Request(f"http://127.0.0.1:{port}{path}", headers={"Connection": "close"})
    try:
        with urlopen(request, timeout=20) as response:
            return int(response.status), json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        payload = json.loads(exc.read().decode("utf-8"))
        return int(exc.code), payload
    except URLError as exc:
        raise RuntimeError(f"HTTP request failed: {type(exc.reason).__name__}") from exc


def start_worker(port: int, temp_root: Path, redis_url: str, namespace: str) -> subprocess.Popen:
    env = os.environ.copy()
    env.update(
        {
            "MARKET_PULSE_HOST": "127.0.0.1",
            "MARKET_PULSE_PORT": str(port),
            "MARKET_PULSE_LOG_LEVEL": "CRITICAL",
            "MARKET_PULSE_REDIS_URL": redis_url,
            "MARKET_PULSE_SHARED_STATE_NAMESPACE": namespace,
            "MARKET_PULSE_RATE_LIMIT_MODE": "redis",
            "MARKET_PULSE_CACHE_L2_MODE": "redis",
            "MARKET_PULSE_SINGLE_FLIGHT_MODE": "redis",
            "MARKET_PULSE_BACKGROUND_LEASE_MODE": "redis",
            "MARKET_PULSE_API_RATE_LIMIT_PER_MINUTE": "1",
            "MARKET_PULSE_DISABLE_BACKGROUND": "1",
            "DERIVATIVES_DB_PATH": str(temp_root / f"worker-{port}.sqlite3"),
            "MARKET_PULSE_CACHE_FILE": str(temp_root / f"worker-{port}-cache.json"),
            "DERIVATIVES_ADMIN_TOKEN": "td03-local-canary-token",
        }
    )
    return subprocess.Popen(
        [sys.executable, str(ROOT / "app.py")],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def main() -> int:
    redis_url = os.environ.get("MARKET_PULSE_REDIS_URL", "").strip()
    if not redis_url:
        raise SystemExit("MARKET_PULSE_REDIS_URL is required")
    namespace = f"market-pulse:staging:td03-http-20260901:{uuid.uuid4().hex}"
    ports = (free_port(), free_port())
    workers: list[subprocess.Popen] = []
    with tempfile.TemporaryDirectory(prefix="market_pulse_td03_http_") as temp_name:
        temp_root = Path(temp_name)
        try:
            workers = [start_worker(port, temp_root, redis_url, namespace) for port in ports]
            for port in ports:
                wait_health(port)

            page_status, _ = get_json(ports[0], "/api/derivatives/v1-status")
            if page_status != 200:
                raise AssertionError(f"first worker API canary failed: {page_status}")
            limited_status, limited_payload = get_json(ports[1], "/api/derivatives/v1-status")
            if limited_status != 429 or limited_payload.get("error_code") != "RATE_LIMITED":
                raise AssertionError(f"cross-worker rate-limit consistency failed: {limited_status}, {limited_payload!r}")

            health_status_a, _ = get_json(ports[0], "/api/health")
            health_status_b, _ = get_json(ports[1], "/api/health")
            if health_status_a != 200 or health_status_b != 200:
                raise AssertionError("health endpoint was not exempt on both workers")

            print(json.dumps({
                "status": "pass",
                "workers": 2,
                "ports": list(ports),
                "health_both_workers": True,
                "cross_worker_rate_limit": "first accepted, second 429",
                "temp_data_boundary": "isolated per-worker SQLite/cache paths",
            }, ensure_ascii=False, indent=2, sort_keys=True))
            print("TD03_HTTP_DUAL_PROCESS_CANARY_OK")
            return 0
        finally:
            for worker in workers:
                if worker.poll() is None:
                    worker.terminate()
            for worker in workers:
                try:
                    worker.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    worker.kill()
                    worker.wait(timeout=10)


if __name__ == "__main__":
    raise SystemExit(main())
