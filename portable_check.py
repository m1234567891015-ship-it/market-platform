from __future__ import annotations

import json
import logging
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import unquote, urlsplit
from urllib.error import HTTPError
from urllib.request import urlopen

from market_config import ASSET_STATIC_FILES, PAGE_ROUTES, ROOT_STATIC_FILES


BASE_DIR = Path(__file__).resolve().parent
PORT = os.environ.get("MARKET_PULSE_PORT") or "5055"
BASE_URL = f"http://127.0.0.1:{PORT}"
HTML_PAGES = sorted(set(PAGE_ROUTES.values()))
PAGES = sorted(
    {
        *PAGE_ROUTES.keys(),
        "/manifest.webmanifest",
        "/service-worker.js",
        *(f"/{filename}" for filename in ROOT_STATIC_FILES),
        *(f"/assets/{filename}" for filename in ASSET_STATIC_FILES),
    }
)
LOCAL_LINK_SKIP_PREFIXES = (
    "#",
    "//",
    "data:",
    "mailto:",
    "tel:",
    "javascript:",
    "blob:",
)
EXTERNAL_DATA_PATHS = {"/twse-data.js", "/api/twse/site-data", "/api/twse/search"}
LOGGER = logging.getLogger("market_pulse.portable_check")


def read_url(path: str, timeout: int = 30) -> tuple[int, bytes]:
    try:
        with urlopen(f"{BASE_URL}{path}", timeout=timeout) as response:
            return response.status, response.read()
    except HTTPError as exc:
        return exc.code, exc.read()


def is_safe_external_failure(path: str, status: int, body: bytes) -> bool:
    route = urlsplit(path).path
    if route not in EXTERNAL_DATA_PATHS or status not in {502, 503, 504}:
        return False
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False
    return payload.get("success") is False and bool(payload.get("error_code")) and "request_context" in payload


def pick_free_port(start: int = 5055, attempts: int = 100) -> str:
    for port in range(start, start + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return str(port)
    raise RuntimeError(f"No free local port found from {start} to {start + attempts - 1}.")


def normalize_local_target(target: str) -> str | None:
    clean = target.strip().strip('"').strip("'")
    if not clean or clean.startswith(LOCAL_LINK_SKIP_PREFIXES):
        return None
    parts = urlsplit(clean)
    if parts.scheme or parts.netloc:
        return None
    if not parts.path:
        return None
    query = f"?{parts.query}" if parts.query else ""
    return f"{unquote(parts.path)}{query}"


def verify_local_file(page_name: str, target: str) -> str | None:
    normalized = normalize_local_target(target)
    if not normalized:
        return None
    path_part = normalized.split("?", 1)[0].split("#", 1)[0]
    if path_part.startswith("/"):
        return None
    candidate = ((BASE_DIR / page_name).parent / path_part).resolve()
    try:
        candidate.relative_to(BASE_DIR)
    except ValueError:
        return f"{page_name}: local link escapes project root: {target}"
    if not candidate.exists():
        return f"{page_name}: missing local link target {path_part}"
    return None


def collect_root_urls_from_html(html: str) -> set[str]:
    urls: set[str] = set()
    for target in re.findall(r"""(?:href|src)=["']([^"']+)["']""", html):
        normalized = normalize_local_target(target)
        if normalized and normalized.startswith("/"):
            urls.add(normalized)
    return urls


def collect_css_local_files(css_name: str, css: str) -> list[str]:
    failures: list[str] = []
    for raw_target in re.findall(r"""url\(([^)]+)\)""", css):
        target = raw_target.strip()
        failure = verify_local_file(css_name, target)
        if failure:
            failures.append(failure)
    return failures


def print_log_tail(log_path: Path, max_lines: int = 20) -> None:
    """啟動失敗(非零退出或 health 檢查逾時)時,把 app.py 子行程的
    stdout/stderr 尾端印到主控台,取代先前導向 DEVNULL 後、失敗時
    完全無訊息可查的狀況。成功路徑不呼叫本函式,維持安靜。"""
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        print(f"(unable to read backend log {log_path}: {exc})")
        return
    if not lines:
        print("(backend produced no stdout/stderr output)")
        return
    tail = lines[-max_lines:]
    print(f"--- backend log tail (last {len(tail)} of {len(lines)} lines) ---")
    for line in tail:
        print(line)
    print("--- end backend log tail ---")


def main() -> int:
    global BASE_URL, PORT
    PORT = os.environ.get("MARKET_PULSE_PORT") or pick_free_port()
    BASE_URL = f"http://127.0.0.1:{PORT}"
    env = os.environ.copy()
    env["MARKET_PULSE_HOST"] = "127.0.0.1"
    env["MARKET_PULSE_PORT"] = PORT
    env["MARKET_PULSE_DISABLE_BACKGROUND"] = "1"
    runtime_dir = Path(tempfile.mkdtemp(prefix="market_pulse_portable_runtime_"))
    env["DERIVATIVES_DB_PATH"] = str(runtime_dir / "derivatives-platform.sqlite3")
    env["MARKET_PULSE_CACHE_FILE"] = str(runtime_dir / "twse-cache.json")

    log_fd, log_path_str = tempfile.mkstemp(prefix="portable_check_backend_", suffix=".log")
    log_path = Path(log_path_str)
    os.close(log_fd)
    log_file = log_path.open("wb")
    process = subprocess.Popen(
        [sys.executable, "app.py"],
        cwd=BASE_DIR,
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )
    failures: list[str] = []
    external_fallbacks: list[str] = []
    checked_urls: set[str] = set()
    server_ready = False
    try:
        for _ in range(40):
            if process.poll() is not None:
                failures.append(f"Backend process exited early with code {process.returncode}.")
                break
            try:
                status, _ = read_url("/api/health", timeout=2)
                if status == 200:
                    server_ready = True
                    break
            except Exception as exc:
                LOGGER.debug(
                    "portable health probe failed; attempt=%s/40 endpoint=%s",
                    _ + 1,
                    "/api/health",
                    exc_info=exc,
                )
                time.sleep(0.5)
        else:
            failures.append("Server did not become ready (health check timed out).")

        if server_ready:
            checked_urls = set(PAGES)
            for page_name in HTML_PAGES:
                page_path = BASE_DIR / page_name
                try:
                    html = page_path.read_text(encoding="utf-8")
                except Exception as exc:
                    failures.append(f"{page_name}: cannot read UTF-8 HTML ({exc}).")
                    continue
                checked_urls.update(collect_root_urls_from_html(html))
                for target in re.findall(r"""(?:href|src)=["']([^"']+)["']""", html):
                    failure = verify_local_file(page_name, target)
                    if failure:
                        failures.append(failure)

            for css_name in sorted(ROOT_STATIC_FILES):
                if not css_name.endswith(".css"):
                    continue
                css_path = BASE_DIR / css_name
                try:
                    failures.extend(collect_css_local_files(css_name, css_path.read_text(encoding="utf-8")))
                except Exception as exc:
                    failures.append(f"{css_name}: cannot read UTF-8 CSS ({exc}).")

            for path in sorted(checked_urls):
                try:
                    status, body = read_url(path)
                    if is_safe_external_failure(path, status, body):
                        external_fallbacks.append(f"{path}: upstream unavailable (safe API fallback)")
                        continue
                    if status != 200 or not body:
                        failures.append(f"{path}: HTTP {status}, empty={not body}")
                except Exception as exc:
                    failures.append(f"{path}: {exc}")

            try:
                status, body = read_url("/api/twse/search?q=2330")
                if is_safe_external_failure("/api/twse/search?q=2330", status, body):
                    external_fallbacks.append("/api/twse/search?q=2330: upstream unavailable (safe API fallback)")
                else:
                    payload = json.loads(body.decode("utf-8"))
                    if status != 200 or not payload.get("results"):
                        failures.append("/api/twse/search?q=2330 returned no results.")
            except Exception as exc:
                failures.append(f"Stock search API: {exc}")

    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        log_file.close()
        shutil.rmtree(runtime_dir, ignore_errors=True)

    if failures:
        print("Portable check failed:")
        for failure in failures:
            print(f"- {failure}")
        if not server_ready:
            print_log_tail(log_path)
        log_path.unlink(missing_ok=True)
        return 1

    log_path.unlink(missing_ok=True)
    if external_fallbacks:
        print("Portable check note: external data fallback observed:")
        for fallback in sorted(set(external_fallbacks)):
            print(f"- {fallback}")
    print(
        "Portable check passed: "
        f"{len(HTML_PAGES)} HTML pages, {len(checked_urls)} URLs/assets, health API, "
        "stock search API, and local links are available."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
