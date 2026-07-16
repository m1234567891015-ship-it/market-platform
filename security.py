"""Security-layer functions extracted from app.py (TD-01 slice 1).

Covers: response security headers, per-client API rate limiting, the admin-token
guard for the institution-import endpoint, and the verified/unverified SSL fallback
used by outbound market-data fetchers.

app.py wires the two Flask hooks explicitly (app.after_request(add_security_headers),
app.before_request(enforce_api_rate_limit)) rather than this module decorating a
Flask app object directly, so this module has no dependency on the app.py module at
import time.
"""
from __future__ import annotations

import hmac
import logging
import os
import ssl
import threading
import time
from datetime import datetime, timedelta, timezone
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import certifi
from flask import Response, jsonify, request

LOGGER = logging.getLogger("market_pulse")
try:
    TZ = ZoneInfo("Asia/Taipei")
except ZoneInfoNotFoundError:
    TZ = timezone(timedelta(hours=8))

API_RATE_LIMIT_WINDOW_SECONDS = 60
API_RATE_LIMIT_PER_WINDOW = max(0, int(os.environ.get("MARKET_PULSE_API_RATE_LIMIT_PER_MINUTE", "120")))
API_RATE_LIMIT_STATE: dict[str, list[float]] = {}
API_RATE_LIMIT_LAST_CLEANUP = 0.0
API_RATE_LIMIT_LOCK = threading.Lock()
API_RATE_LIMIT_EXEMPT_PATHS = {"/api/health"}


def api_client_identity() -> str:
    return str(request.remote_addr or "unknown")


def cleanup_api_rate_limit_state(now: float) -> None:
    global API_RATE_LIMIT_LAST_CLEANUP
    if now - API_RATE_LIMIT_LAST_CLEANUP < API_RATE_LIMIT_WINDOW_SECONDS:
        return
    for key in list(API_RATE_LIMIT_STATE):
        recent = [
            timestamp for timestamp in API_RATE_LIMIT_STATE.get(key, [])
            if now - timestamp < API_RATE_LIMIT_WINDOW_SECONDS
        ]
        if recent:
            API_RATE_LIMIT_STATE[key] = recent
        else:
            API_RATE_LIMIT_STATE.pop(key, None)
    API_RATE_LIMIT_LAST_CLEANUP = now


def add_security_headers(response: Response) -> Response:
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "manifest-src 'self'; "
        "worker-src 'self'; "
        "base-uri 'self'; "
        "frame-ancestors 'none'",
    )
    response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    if request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


def enforce_api_rate_limit():
    if (
        API_RATE_LIMIT_PER_WINDOW <= 0
        or not request.path.startswith("/api/")
        or request.path in API_RATE_LIMIT_EXEMPT_PATHS
    ):
        return None

    now = time.monotonic()
    client_key = api_client_identity()
    with API_RATE_LIMIT_LOCK:
        cleanup_api_rate_limit_state(now)
        recent = [
            timestamp for timestamp in API_RATE_LIMIT_STATE.get(client_key, [])
            if now - timestamp < API_RATE_LIMIT_WINDOW_SECONDS
        ]
        if len(recent) >= API_RATE_LIMIT_PER_WINDOW:
            retry_after = max(1, int(API_RATE_LIMIT_WINDOW_SECONDS - (now - recent[0])))
            response = jsonify(
                {
                    "success": False,
                    "error_code": "RATE_LIMITED",
                    "error": {"code": "RATE_LIMITED", "message": "請求過於頻繁，請稍後再試"},
                }
            )
            response.status_code = 429
            response.headers["Retry-After"] = str(retry_after)
            return response
        recent.append(now)
        API_RATE_LIMIT_STATE[client_key] = recent
    return None


def is_authorized_derivatives_admin() -> bool:
    expected = str(os.environ.get("DERIVATIVES_ADMIN_TOKEN") or "").strip()
    if not expected:
        return False
    provided = str(
        request.headers.get("X-Admin-Token")
        or request.headers.get("X-Derivatives-Admin-Token")
        or ""
    ).strip()
    return bool(provided) and hmac.compare_digest(provided, expected)


def _is_ssl_error(exc: Exception) -> bool:
    """Return True if *exc* is (or wraps) an SSL certificate verification error."""
    if isinstance(exc, ssl.SSLCertVerificationError):
        return True
    if isinstance(exc, URLError) and isinstance(exc.reason, ssl.SSLCertVerificationError):
        return True
    message_parts = [type(exc).__name__]
    reason = getattr(exc, "reason", None)
    if reason is not None:
        message_parts.append(type(reason).__name__)
        message_parts.extend(str(arg) for arg in getattr(reason, "args", ()) if arg is not None)
    message_parts.extend(str(arg) for arg in getattr(exc, "args", ()) if arg is not None)
    message = " ".join(message_parts)
    if "CERTIFICATE_VERIFY_FAILED" in message or "certificate verify failed" in message.lower():
        return True
    return False


def _is_production_environment() -> bool:
    explicit_env = str(os.environ.get("MARKET_PULSE_ENV") or os.environ.get("FLASK_ENV") or "").lower()
    return explicit_env == "production" or any(
        os.environ.get(name)
        for name in ("RENDER", "RENDER_SERVICE_ID", "RENDER_EXTERNAL_URL")
    )


_verified_ssl_context: ssl.SSLContext | None = None
_verified_ssl_context_lock = threading.Lock()


def _get_verified_ssl_context() -> ssl.SSLContext:
    """Return a shared, lazily-built verified SSLContext.

    ssl.create_default_context(cafile=...) re-reads and re-parses the whole
    certifi CA bundle from disk (measured ~360ms/call). SSLContext objects
    are safe to share across many connections, so build it once per process
    instead of paying that cost on every single outbound API request.
    """
    global _verified_ssl_context
    if _verified_ssl_context is None:
        with _verified_ssl_context_lock:
            if _verified_ssl_context is None:
                _verified_ssl_context = ssl.create_default_context(cafile=certifi.where())
    return _verified_ssl_context


def _urlopen_with_ssl_fallback(request: Request, timeout: int):
    """Open *request* with certificate verification.

    Unverified fallback is disabled by default.  It can be enabled only for
    explicit maintenance/debug sessions with ALLOW_UNVERIFIED_SSL_FALLBACK=1
    and only for known market-data domains.
    """
    host = (urlsplit(request.full_url).hostname or "").lower()
    allowed_hosts = {
        "www.taifex.com.tw",
        "www.twse.com.tw",
        "openapi.twse.com.tw",
        "www.tpex.org.tw",
        "smart.tdcc.com.tw",
        "query1.finance.yahoo.com",
        "query2.finance.yahoo.com",
        "tw.stock.yahoo.com",
        "home.treasury.gov",
        "fred.stlouisfed.org",
        "tradingeconomics.com",
        "cdn.cboe.com",
    }
    fallback_allowed = (
        os.environ.get("ALLOW_UNVERIFIED_SSL_FALLBACK") == "1"
        or not _is_production_environment()
    )
    if host == "smart.tdcc.com.tw" and fallback_allowed and not _is_production_environment():
        return urlopen(request, timeout=timeout, context=ssl._create_unverified_context())

    try:
        verified_context = _get_verified_ssl_context()
        return urlopen(request, timeout=timeout, context=verified_context)
    except Exception as exc:
        if not _is_ssl_error(exc):
            raise
        if not fallback_allowed or host not in allowed_hosts:
            raise
        if _is_production_environment():
            LOGGER.warning("Blocked unverified SSL fallback in production for host=%s", host)
            raise
        try:
            from app import DERIVATIVES_STORE  # deferred: avoids an app.py <-> security.py import cycle

            DERIVATIVES_STORE.log(
                "WARNING",
                "ssl_fallback",
                f"Unverified SSL fallback used for {host}",
                datetime.now(TZ).isoformat(),
            )
        except Exception as log_exc:
            LOGGER.warning("Failed to persist SSL fallback warning: %s", log_exc)
        LOGGER.debug("Using unverified SSL fallback for host=%s: %s", host, exc)
        return urlopen(request, timeout=timeout, context=ssl._create_unverified_context())
