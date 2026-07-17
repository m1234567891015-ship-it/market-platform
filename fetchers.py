"""Generic HTTP fetch helpers extracted from app.py (TD-01 slice 3, batch 0).

These are the foundational functions ~80% of app.py's 86 `fetch_*` functions
build on: `fetch_json`/`fetch_nasdaq_json`/`post_json` for JSON APIs, and
`fetch_text`/`fetch_binary`/`fetch_form_text` for scraped/CSV/form-POSTed
sources with an optional memory-cache gate (`should_cache_external_text`,
gated to a handful of known-slow/rate-sensitive hosts). All six route outbound
requests through `security.py`'s `_urlopen_with_ssl_fallback`, so this module
is the single place SSL-fallback policy actually gets exercised from.

This batch moves only these generic helpers, not any per-source fetcher yet
(those follow in later batches, grouped by data source: TWSE/TPEX, Yahoo
global, TAIFEX, Yahoo Taiwan, everything else). Three later-batch functions
(`fetch_yahoo_tw_stock_resource`, `fetch_yahoo_options_payload`,
`fetch_barchart_options_context`) intentionally do NOT go through this
module's helpers - they call `_urlopen_with_ssl_fallback` directly or use
their own cookie-jar opener - documented when they move.
"""
from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode, urlsplit
from urllib.request import Request

from cache import read_memory_cache, write_memory_cache
from market_config import NASDAQ_API_BASE, NASDAQ_USER_AGENT, USER_AGENT
from security import _urlopen_with_ssl_fallback

EXTERNAL_TEXT_CACHE_SECONDS = 5 * 60


def should_cache_external_text(url: str) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    return host in {"www.taifex.com.tw", "tw.stock.yahoo.com", "home.treasury.gov", "fred.stlouisfed.org", "tradingeconomics.com"}


def fetch_json(url: str, timeout: int = 30) -> Any:
    headers = {"User-Agent": USER_AGENT}
    if "twse.com.tw" in url:
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json, text/plain, */*",
            "Connection": "close",
        }
    req = Request(url, headers=headers)
    with _urlopen_with_ssl_fallback(req, timeout) as response:
        return json.loads(response.read().decode("utf-8"))
def fetch_nasdaq_json(path: str, timeout: int = 12) -> Any:
    url = path if path.startswith("http") else f"{NASDAQ_API_BASE}{path}"
    req = Request(url, headers={
        "User-Agent": NASDAQ_USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.nasdaq.com",
        "Referer": "https://www.nasdaq.com/",
    })
    with _urlopen_with_ssl_fallback(req, timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def post_json(url: str, payload: dict[str, Any], timeout: int = 30, headers: dict[str, str] | None = None) -> Any:
    body = json.dumps(payload).encode("utf-8")
    request_headers = {
        "User-Agent": USER_AGENT,
        "Content-Type": "application/json",
        **(headers or {}),
    }
    req = Request(url, data=body, headers=request_headers, method="POST")
    with _urlopen_with_ssl_fallback(req, timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_text(url: str, timeout: int = 30) -> str:
    cache_key = f"GET:{url}"
    if should_cache_external_text(url):
        cached = read_memory_cache("external_text", cache_key, EXTERNAL_TEXT_CACHE_SECONDS)
        if cached is not None:
            return str(cached)
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with _urlopen_with_ssl_fallback(req, timeout) as response:
        raw = response.read()
        content_type = str(response.headers.get("Content-Type") or "").lower()
    encoding = "cp950" if "ms950" in content_type or "big5" in content_type else "utf-8"
    text = raw.decode(encoding, errors="ignore")
    if should_cache_external_text(url):
        write_memory_cache("external_text", cache_key, text)
    return text


def fetch_binary(url: str, timeout: int = 30) -> bytes:
    cache_key = f"BIN:{url}"
    if should_cache_external_text(url):
        cached = read_memory_cache("external_text", cache_key, EXTERNAL_TEXT_CACHE_SECONDS)
        if cached is not None:
            return bytes(cached)
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with _urlopen_with_ssl_fallback(req, timeout) as response:
        payload = response.read()
    if should_cache_external_text(url):
        write_memory_cache("external_text", cache_key, payload)
    return payload


def fetch_form_text(url: str, fields: dict[str, str], timeout: int = 30) -> str:
    encoded_fields = urlencode(sorted((str(key), str(value)) for key, value in fields.items()))
    cache_key = f"FORM:{url}:{encoded_fields}"
    if should_cache_external_text(url):
        cached = read_memory_cache("external_text", cache_key, EXTERNAL_TEXT_CACHE_SECONDS)
        if cached is not None:
            return str(cached)
    payload = encoded_fields.encode("utf-8")
    req = Request(
        url,
        data=payload,
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    with _urlopen_with_ssl_fallback(req, timeout) as response:
        raw = response.read()
        content_type = str(response.headers.get("Content-Type") or "").lower()
    encoding = "cp950" if "ms950" in content_type or "big5" in content_type else "utf-8"
    text = raw.decode(encoding, errors="ignore")
    if should_cache_external_text(url):
        write_memory_cache("external_text", cache_key, text)
    return text
