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
import http.client
import logging
import os
import shlex
import ssl
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import HTTPSHandler, Request, build_opener, urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import certifi
from flask import Response, jsonify, request
from shared_state import (
    RedisSharedStateAdapter,
    SharedStateAdapter,
    SharedStateError,
    SharedStateTimeout,
    SharedStateUnavailable,
)

LOGGER = logging.getLogger("market_pulse")
try:
    TZ = ZoneInfo("Asia/Taipei")
except ZoneInfoNotFoundError:
    TZ = timezone(timedelta(hours=8))

API_RATE_LIMIT_WINDOW_SECONDS = 60
API_RATE_LIMIT_PER_WINDOW = max(0, int(os.environ.get("MARKET_PULSE_API_RATE_LIMIT_PER_MINUTE", "120")))
# This state is intentionally process-local while deployment is pinned to one
# worker. Keep hostile/one-off client identities from growing it without bound.
API_RATE_LIMIT_MAX_CLIENTS = max(1, int(os.environ.get("MARKET_PULSE_API_RATE_LIMIT_MAX_CLIENTS", "10000")))
API_RATE_LIMIT_STATE: dict[str, list[float]] = {}
API_RATE_LIMIT_LAST_CLEANUP = 0.0
API_RATE_LIMIT_LOCK = threading.Lock()
API_RATE_LIMIT_EXEMPT_PATHS = {"/api/health"}
API_RATE_LIMIT_SHARED_ADAPTER: SharedStateAdapter | None = None
API_RATE_LIMIT_SHARED_ADAPTER_LOCK = threading.Lock()
API_RATE_LIMIT_SHARED_NAMESPACE = os.environ.get("MARKET_PULSE_SHARED_STATE_NAMESPACE", "market-pulse:v1")
API_RATE_LIMIT_SHARED_TIMEOUT_SECONDS = max(
    0.1,
    float(os.environ.get("MARKET_PULSE_SHARED_STATE_TIMEOUT_SECONDS", "1")),
)


def api_client_identity() -> str:
    return str(request.remote_addr or "unknown")


def cleanup_api_rate_limit_state(now: float) -> None:
    global API_RATE_LIMIT_LAST_CLEANUP
    if (
        now - API_RATE_LIMIT_LAST_CLEANUP < API_RATE_LIMIT_WINDOW_SECONDS
        and len(API_RATE_LIMIT_STATE) <= API_RATE_LIMIT_MAX_CLIENTS
    ):
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
    overflow = len(API_RATE_LIMIT_STATE) - API_RATE_LIMIT_MAX_CLIENTS
    if overflow > 0:
        oldest_clients = sorted(
            API_RATE_LIMIT_STATE.items(),
            key=lambda item: max(item[1]) if item[1] else float("-inf"),
        )[:overflow]
        for key, _timestamps in oldest_clients:
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


def is_rate_limit_exempt_request() -> bool:
    return (
        API_RATE_LIMIT_PER_WINDOW <= 0
        or not request.path.startswith("/api/")
        or request.path in API_RATE_LIMIT_EXEMPT_PATHS
    )


def register_rate_limit_window_hit(client_key: str, now: float) -> int | None:
    """Record a hit for *client_key* in the sliding window.

    Returns the Retry-After seconds if the client is over the limit, else None.
    """
    with API_RATE_LIMIT_LOCK:
        cleanup_api_rate_limit_state(now)
        recent = [
            timestamp for timestamp in API_RATE_LIMIT_STATE.get(client_key, [])
            if now - timestamp < API_RATE_LIMIT_WINDOW_SECONDS
        ]
        if len(recent) >= API_RATE_LIMIT_PER_WINDOW:
            return max(1, int(API_RATE_LIMIT_WINDOW_SECONDS - (now - recent[0])))
        recent.append(now)
        API_RATE_LIMIT_STATE[client_key] = recent
        cleanup_api_rate_limit_state(now)
        return None


def rate_limit_backend_mode(environ: dict[str, str] | None = None) -> str:
    """Return the explicitly selected H-05-03 mode, defaulting to local."""
    environ = environ if environ is not None else os.environ
    mode = str(environ.get("MARKET_PULSE_RATE_LIMIT_MODE", "local")).strip().lower()
    return mode if mode in {"local", "shadow", "redis"} else "local"


def _build_rate_limit_shared_adapter() -> SharedStateAdapter:
    redis_url = str(os.environ.get("MARKET_PULSE_REDIS_URL") or "").strip()
    if not redis_url:
        raise SharedStateUnavailable("MARKET_PULSE_REDIS_URL is required for shared rate limiting")
    try:
        import redis
    except ImportError as exc:
        raise SharedStateUnavailable("redis package is required for shared rate limiting") from exc
    try:
        client = redis.Redis.from_url(
            redis_url,
            protocol=2,
            socket_connect_timeout=API_RATE_LIMIT_SHARED_TIMEOUT_SECONDS,
            socket_timeout=API_RATE_LIMIT_SHARED_TIMEOUT_SECONDS,
            decode_responses=True,
        )
        client.ping()
    except TimeoutError as exc:
        raise SharedStateTimeout("Redis rate-limit health check timed out") from exc
    except Exception as exc:
        raise SharedStateUnavailable("Redis rate-limit health check failed") from exc
    return RedisSharedStateAdapter(client, namespace=API_RATE_LIMIT_SHARED_NAMESPACE)


def _get_rate_limit_shared_adapter() -> SharedStateAdapter:
    global API_RATE_LIMIT_SHARED_ADAPTER
    if API_RATE_LIMIT_SHARED_ADAPTER is not None:
        return API_RATE_LIMIT_SHARED_ADAPTER
    with API_RATE_LIMIT_SHARED_ADAPTER_LOCK:
        if API_RATE_LIMIT_SHARED_ADAPTER is None:
            API_RATE_LIMIT_SHARED_ADAPTER = _build_rate_limit_shared_adapter()
        return API_RATE_LIMIT_SHARED_ADAPTER


def _register_shared_rate_limit_window_hit(client_key: str) -> int | None:
    adapter = _get_rate_limit_shared_adapter()
    return adapter.rate_limit_hit(
        client_key,
        time.time(),
        API_RATE_LIMIT_WINDOW_SECONDS,
        API_RATE_LIMIT_PER_WINDOW,
        API_RATE_LIMIT_MAX_CLIENTS,
    )


def build_rate_limit_backend_unavailable_response() -> Response:
    response = jsonify(
        {
            "success": False,
            "error_code": "RATE_LIMIT_BACKEND_UNAVAILABLE",
            "error": {"code": "RATE_LIMIT_BACKEND_UNAVAILABLE", "message": "服務暫時無法處理請求，請稍後再試"},
        }
    )
    response.status_code = 503
    response.headers["Retry-After"] = "5"
    return response


def build_rate_limit_exceeded_response(retry_after: int) -> Response:
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


def enforce_api_rate_limit():
    if is_rate_limit_exempt_request():
        return None

    client_key = api_client_identity()
    mode = rate_limit_backend_mode()
    if mode == "local":
        retry_after = register_rate_limit_window_hit(client_key, time.monotonic())
    elif mode == "shadow":
        local_retry_after = register_rate_limit_window_hit(client_key, time.monotonic())
        try:
            shared_retry_after = _register_shared_rate_limit_window_hit(client_key)
            LOGGER.info(
                "rate_limit_shadow_compare local_limited=%s shared_limited=%s match=%s",
                local_retry_after is not None,
                shared_retry_after is not None,
                (local_retry_after is None) == (shared_retry_after is None),
            )
        except SharedStateError as exc:
            LOGGER.warning("rate_limit_shadow_backend_error error_type=%s", type(exc).__name__)
        retry_after = local_retry_after
    else:
        try:
            retry_after = _register_shared_rate_limit_window_hit(client_key)
        except SharedStateError as exc:
            LOGGER.error("rate_limit_shared_backend_unavailable error_type=%s", type(exc).__name__)
            return build_rate_limit_backend_unavailable_response()
    if retry_after is not None:
        return build_rate_limit_exceeded_response(retry_after)
    return None


def configured_worker_count(argv: list[str] | None = None, environ: dict[str, str] | None = None) -> int | None:
    """Return an explicitly configured Gunicorn worker count, if detectable."""
    environ = environ if environ is not None else os.environ
    args = list(argv if argv is not None else sys.argv)
    command_name = os.path.basename(args[0]).lower() if args else ""
    gunicorn_env = str(environ.get("GUNICORN_CMD_ARGS") or "").strip()
    if "gunicorn" not in command_name and not gunicorn_env:
        return None

    candidates = args[1:] + shlex.split(gunicorn_env)
    for index, argument in enumerate(candidates):
        if argument in {"--workers", "-w"} and index + 1 < len(candidates):
            try:
                return int(candidates[index + 1])
            except ValueError:
                continue
        if argument.startswith("--workers=") or argument.startswith("-w="):
            try:
                return int(argument.split("=", 1)[1])
            except ValueError:
                continue

    for env_name in ("WEB_CONCURRENCY", "GUNICORN_WORKERS"):
        value = str(environ.get(env_name) or "").strip()
        if value:
            try:
                return int(value)
            except ValueError:
                return None
    return None


def warn_if_multi_worker() -> None:
    worker_count = configured_worker_count()
    if worker_count is not None and worker_count > 1:
        LOGGER.warning(
            "Local rate-limit/cache/in-flight state is process-local; configured workers=%d. "
            "Use one worker or move shared state to an external store before scaling out.",
            worker_count,
        )


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
INSTITUTION_PROVIDER_HOST = "openapi.taifex.com.tw"


def _get_verified_ssl_context() -> ssl.SSLContext:
    """Return a shared, lazily-built verified SSLContext.

    ssl.create_default_context(cafile=...) re-reads and re-parses the whole
    certifi CA bundle from disk (measured ~360ms/call). SSLContext objects
    are safe to share across many connections, so build it once per process
    instead of paying that cost on every single outbound API request.
    """
    global _verified_ssl_context
    state = _active_institution_observability_state()
    _shared_ssl_context_observe("ssl_context.shared.enter", state=state)
    _institution_provider_observe(
        state,
        "institution.provider.ssl_context.enter",
        provider="taifex",
        provider_host=INSTITUTION_PROVIDER_HOST,
    )
    if _verified_ssl_context is None:
        _shared_ssl_context_observe("ssl_context.shared.lock_wait.begin", state=state)
        lock_acquired = False
        try:
            with _verified_ssl_context_lock:
                lock_acquired = True
                _shared_ssl_context_observe("ssl_context.shared.lock_acquired", state=state)
                _institution_provider_observe(
                    state,
                    "institution.provider.ssl_context.lock_acquired",
                    provider="taifex",
                    provider_host=INSTITUTION_PROVIDER_HOST,
                )
                if _verified_ssl_context is None:
                    _shared_ssl_context_observe("ssl_context.shared.create.begin", state=state)
                    _institution_provider_observe(
                        state,
                        "institution.provider.ssl_context.create.begin",
                        provider="taifex",
                        provider_host=INSTITUTION_PROVIDER_HOST,
                    )
                    _verified_ssl_context = ssl.create_default_context(cafile=certifi.where())
                    _shared_ssl_context_observe("ssl_context.shared.create.end", state=state)
                    _institution_provider_observe(
                        state,
                        "institution.provider.ssl_context.create.end",
                        provider="taifex",
                        provider_host=INSTITUTION_PROVIDER_HOST,
                    )
        finally:
            if lock_acquired:
                _shared_ssl_context_observe("ssl_context.shared.lock_released", state=state)
    _shared_ssl_context_observe("ssl_context.shared.return", state=state)
    _institution_provider_observe(
        state,
        "institution.provider.ssl_context.return",
        provider="taifex",
        provider_host=INSTITUTION_PROVIDER_HOST,
    )
    return _verified_ssl_context


def _active_institution_observability_state() -> dict[str, object] | None:
    from flask import g, has_request_context

    if not has_request_context():
        return None
    state = getattr(g, "institution_observability", None)
    return state if isinstance(state, dict) else None


def _institution_observability_enabled(request: Request) -> bool:
    host = (urlsplit(request.full_url).hostname or "").lower()
    return host == INSTITUTION_PROVIDER_HOST and _active_institution_observability_state() is not None


def _institution_provider_observe(
    state: dict[str, object] | None,
    event: str,
    **fields: object,
) -> None:
    if state is None:
        return
    try:
        from app import institution_observability_log

        institution_observability_log(event, state=state, **fields)
    except Exception:
        # Observability must never change the provider's return or exception semantics.
        return


def _shared_ssl_context_observe(
    event: str,
    *,
    state: dict[str, object] | None,
) -> None:
    """Record shared SSL-context lifecycle without affecting SSL behavior."""
    try:
        from flask import has_request_context

        thread_id = threading.get_ident()
        thread_name = threading.current_thread().name
        request_context = "true" if has_request_context() else "false"
        fields = {
            "thread_id": thread_id,
            "thread_name": thread_name,
            "request_context": request_context,
        }
        if state is not None:
            from app import institution_observability_log

            institution_observability_log(event, state=state, **fields)
        else:
            LOGGER.info(
                "event=%s thread_id=%s thread_name=%s request_context=%s",
                event,
                thread_id,
                thread_name,
                request_context,
            )
    except Exception:
        return


def _classify_institution_pre_response_events(events: list[str]) -> str:
    """Classify the first observable pre-response boundary from event names."""
    names = set(events)

    def has_open_stage(begin_event: str, terminal_event: str) -> bool:
        depth = 0
        for event in events:
            if event == begin_event:
                depth += 1
            elif event == terminal_event and depth:
                depth -= 1
        return depth > 0

    if "institution.provider.dns_tcp.begin" in names and "institution.provider.dns_tcp.end" not in names:
        return "DNS_OR_TCP_CONNECT"
    if (
        "institution.provider.dns_tcp.end" in names
        and "institution.provider.proxy_tunnel.begin" in names
        and "institution.provider.proxy_tunnel.end" not in names
    ):
        return "PROXY_CONNECT"
    if (
        "institution.provider.dns_tcp.end" in names
        and (
            "institution.provider.proxy_tunnel.begin" not in names
            or "institution.provider.proxy_tunnel.end" in names
        )
        and "institution.provider.https_connect.begin" in names
        and "institution.provider.https_connect.end" not in names
    ):
        return "TLS_HANDSHAKE_PATH"
    if (
        "institution.provider.https_connect.end" in names
        and has_open_stage(
            "institution.provider.request_send.begin",
            "institution.provider.request_send.end",
        )
    ):
        return "REQUEST_SEND"
    if (
        "institution.provider.request_send.end" in names
        and "institution.provider.response_headers.begin" in names
        and has_open_stage(
            "institution.provider.response_headers.begin",
            "institution.provider.response_headers.end",
        )
    ):
        return "RESPONSE_HEADERS"
    if (
        "institution.provider.response_headers.end" in names
        and "institution.provider.urlopen.opened" in names
    ):
        return "PRE_RESPONSE_COMPLETES"
    return "NOT_VERIFIED"


class _InstitutionObservabilityHTTPSConnection(http.client.HTTPSConnection):
    """Request-scoped delegation wrappers for the Institution provider path."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._institution_observability_state = _active_institution_observability_state()
        self._institution_send_seq = 0
        if self._institution_observability_state is not None:
            original_create_connection = self._create_connection

            def observed_create_connection(*connection_args, **connection_kwargs):
                state = self._institution_observability_state
                _institution_provider_observe(
                    state,
                    "institution.provider.dns_tcp.begin",
                    provider="taifex",
                    provider_host=INSTITUTION_PROVIDER_HOST,
                )
                try:
                    result = original_create_connection(*connection_args, **connection_kwargs)
                except BaseException as exc:
                    _institution_provider_observe(
                        state,
                        "institution.provider.dns_tcp.exception",
                        provider="taifex",
                        provider_host=INSTITUTION_PROVIDER_HOST,
                        exception_class=type(exc).__name__,
                    )
                    raise
                _institution_provider_observe(
                    state,
                    "institution.provider.dns_tcp.end",
                    provider="taifex",
                    provider_host=INSTITUTION_PROVIDER_HOST,
                )
                return result

            self._create_connection = observed_create_connection

    def _tunnel(self, *args, **kwargs):
        if getattr(self, "_tunnel_host", None) is None:
            return super()._tunnel(*args, **kwargs)
        state = self._institution_observability_state
        _institution_provider_observe(
            state,
            "institution.provider.proxy_tunnel.begin",
            provider="taifex",
            provider_host=INSTITUTION_PROVIDER_HOST,
            proxy_active="true",
        )
        try:
            result = super()._tunnel(*args, **kwargs)
        except BaseException as exc:
            _institution_provider_observe(
                state,
                "institution.provider.proxy_tunnel.exception",
                provider="taifex",
                provider_host=INSTITUTION_PROVIDER_HOST,
                proxy_active="true",
                exception_class=type(exc).__name__,
            )
            raise
        _institution_provider_observe(
            state,
            "institution.provider.proxy_tunnel.end",
            provider="taifex",
            provider_host=INSTITUTION_PROVIDER_HOST,
            proxy_active="true",
        )
        return result

    def connect(self):
        state = self._institution_observability_state
        _institution_provider_observe(
            state,
            "institution.provider.https_connect.begin",
            provider="taifex",
            provider_host=INSTITUTION_PROVIDER_HOST,
        )
        try:
            result = super().connect()
        except BaseException as exc:
            _institution_provider_observe(
                state,
                "institution.provider.https_connect.exception",
                provider="taifex",
                provider_host=INSTITUTION_PROVIDER_HOST,
                exception_class=type(exc).__name__,
            )
            raise
        _institution_provider_observe(
            state,
            "institution.provider.https_connect.end",
            provider="taifex",
            provider_host=INSTITUTION_PROVIDER_HOST,
        )
        return result

    def send(self, data):
        self._institution_send_seq += 1
        state = self._institution_observability_state
        send_seq = self._institution_send_seq
        _institution_provider_observe(
            state,
            "institution.provider.request_send.begin",
            provider="taifex",
            provider_host=INSTITUTION_PROVIDER_HOST,
            send_seq=send_seq,
        )
        try:
            result = super().send(data)
        except BaseException as exc:
            _institution_provider_observe(
                state,
                "institution.provider.request_send.exception",
                provider="taifex",
                provider_host=INSTITUTION_PROVIDER_HOST,
                send_seq=send_seq,
                exception_class=type(exc).__name__,
            )
            raise
        _institution_provider_observe(
            state,
            "institution.provider.request_send.end",
            provider="taifex",
            provider_host=INSTITUTION_PROVIDER_HOST,
            send_seq=send_seq,
        )
        return result

    def getresponse(self):
        state = self._institution_observability_state
        _institution_provider_observe(
            state,
            "institution.provider.response_headers.begin",
            provider="taifex",
            provider_host=INSTITUTION_PROVIDER_HOST,
        )
        try:
            result = super().getresponse()
        except BaseException as exc:
            _institution_provider_observe(
                state,
                "institution.provider.response_headers.exception",
                provider="taifex",
                provider_host=INSTITUTION_PROVIDER_HOST,
                exception_class=type(exc).__name__,
            )
            raise
        _institution_provider_observe(
            state,
            "institution.provider.response_headers.end",
            provider="taifex",
            provider_host=INSTITUTION_PROVIDER_HOST,
        )
        return result


class _InstitutionObservabilityHTTPSHandler(HTTPSHandler):
    def https_open(self, req):
        if _institution_observability_enabled(req):
            return self.do_open(
                _InstitutionObservabilityHTTPSConnection,
                req,
                context=self._context,
            )
        return super().https_open(req)


def _urlopen_with_institution_observability(request: Request, timeout: int, context: ssl.SSLContext):
    opener = build_opener(_InstitutionObservabilityHTTPSHandler(context=context))
    return opener.open(request, timeout=timeout)


def _urlopen_with_ssl_fallback(request: Request, timeout: int):
    """Open *request* with certificate verification.

    Unverified fallback is disabled by default.  It can be enabled only for
    explicit maintenance/debug sessions with ALLOW_UNVERIFIED_SSL_FALLBACK=1
    and only for known market-data domains - this opt-in is required in
    every environment, not auto-granted outside production (TD-07: closed a
    gap where any non-production environment silently allowed fallback with
    no explicit flag, and smart.tdcc.com.tw skipped verification
    unconditionally in non-production without even attempting a verified
    connection first).
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
    fallback_allowed = os.environ.get("ALLOW_UNVERIFIED_SSL_FALLBACK") == "1"

    try:
        verified_context = _get_verified_ssl_context()
        if _institution_observability_enabled(request):
            return _urlopen_with_institution_observability(request, timeout, verified_context)
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
        LOGGER.warning("Using unverified SSL fallback for host=%s: %s", host, exc)
        return urlopen(request, timeout=timeout, context=ssl._create_unverified_context())
