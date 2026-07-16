from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import unquote, urlsplit
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


def read_url(path: str, timeout: int = 30) -> tuple[int, bytes]:
    with urlopen(f"{BASE_URL}{path}", timeout=timeout) as response:
        return response.status, response.read()


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


def main() -> int:
    global BASE_URL, PORT
    PORT = os.environ.get("MARKET_PULSE_PORT") or pick_free_port()
    BASE_URL = f"http://127.0.0.1:{PORT}"
    env = os.environ.copy()
    env["MARKET_PULSE_HOST"] = "127.0.0.1"
    env["MARKET_PULSE_PORT"] = PORT
    env["MARKET_PULSE_DISABLE_BACKGROUND"] = "1"
    process = subprocess.Popen(
        [sys.executable, "app.py"],
        cwd=BASE_DIR,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    failures: list[str] = []
    try:
        for _ in range(40):
            try:
                status, _ = read_url("/api/health", timeout=2)
                if status == 200:
                    break
            except Exception:
                time.sleep(0.5)
        else:
            failures.append("Server did not become ready.")
            return 1

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
                if status != 200 or not body:
                    failures.append(f"{path}: HTTP {status}, empty={not body}")
            except Exception as exc:
                failures.append(f"{path}: {exc}")

        try:
            status, body = read_url("/api/twse/search?q=2330")
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

    if failures:
        print("Portable check failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(
        "Portable check passed: "
        f"{len(HTML_PAGES)} HTML pages, {len(checked_urls)} URLs/assets, health API, "
        "stock search API, and local links are available."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
