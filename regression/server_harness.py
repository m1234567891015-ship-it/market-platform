"""共用工具:以子行程啟動 app.py,供 capture/verify/frontend 腳本共用。

刻意使用臨時的 DERIVATIVES_DB_PATH 與 MARKET_PULSE_CACHE_FILE,
避免任何一支迴歸腳本讀寫到專案根目錄下受保護的執行期資料檔
(derivatives-platform.sqlite3、twse-cache.json)。
"""
from __future__ import annotations

import http.client
import os
import socket
import subprocess
import sys
import tempfile
import time
from contextlib import closing
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def find_free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class ServerHandle:
    def __init__(self, process: subprocess.Popen, base_url: str, tmpdir: tempfile.TemporaryDirectory):
        self.process = process
        self.base_url = base_url
        self._tmpdir = tmpdir

    def stop(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=10)
        self._tmpdir.cleanup()

    def __enter__(self) -> "ServerHandle":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()


def wait_for_health(host: str, port: int, timeout: float = 60.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            conn = http.client.HTTPConnection(host, port, timeout=2)
            conn.request("GET", "/api/health")
            resp = conn.getresponse()
            resp.read()
            conn.close()
            if resp.status == 200:
                return True
        except (ConnectionRefusedError, OSError, http.client.HTTPException):
            pass
        time.sleep(0.5)
    return False


def start_server(extra_env: dict | None = None, port: int | None = None) -> ServerHandle:
    """啟動一份獨立的 app.py 行程,回傳 ServerHandle(含 base_url)。

    port 預設隨機挑一個空閒埠;frontend_check.py 的 HAR 錄製/重播必須指定
    固定 port,否則基準錄製時的 origin(http://127.0.0.1:<port>)跟重播時
    的 origin 對不上,route_from_har 會判定每個請求都找不到對應紀錄。
    """
    tmpdir = tempfile.TemporaryDirectory(prefix="mp_regression_")
    if port is None:
        port = find_free_port()
    env = os.environ.copy()
    env["MARKET_PULSE_HOST"] = "127.0.0.1"
    env["MARKET_PULSE_PORT"] = str(port)
    env["MARKET_PULSE_LOG_LEVEL"] = "CRITICAL"
    env["DERIVATIVES_DB_PATH"] = str(Path(tmpdir.name) / "regression-baseline.sqlite3")
    env["MARKET_PULSE_CACHE_FILE"] = str(Path(tmpdir.name) / "regression-cache.json")
    env.setdefault("DERIVATIVES_ADMIN_TOKEN", "regression-test-token")
    if extra_env:
        env.update(extra_env)

    process = subprocess.Popen(
        [sys.executable, str(REPO_ROOT / "app.py")],
        cwd=str(REPO_ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    ok = wait_for_health("127.0.0.1", port, timeout=60.0)
    if not ok:
        process.terminate()
        tmpdir.cleanup()
        raise RuntimeError("app.py 未能在時限內回應 /api/health")
    return ServerHandle(process, f"http://127.0.0.1:{port}", tmpdir)
