from __future__ import annotations

import ast
import importlib
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


class GuardrailFailure(AssertionError):
    pass


def read_text(path: str) -> str:
    return (BASE_DIR / path).read_text(encoding="utf-8-sig")


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise GuardrailFailure(message)


def unsafe_dynamic_url_lines(script: str, attribute: str) -> list[str]:
    needle = f'{attribute}="${{'
    safe_prefix = f'{attribute}="${{safeUrl('
    ignored_fragments = ("querySelector",)
    return [
        line.strip()
        for line in script.splitlines()
        if needle in line and safe_prefix not in line and not any(fragment in line for fragment in ignored_fragments)
    ]


def check_frontend_xss_and_url_safety() -> None:
    script = read_text("app.js")
    for required in (
        "function escapeHtml(",
        "function safeUrl(",
        "function sanitizeHtml(",
        "nativeInnerHtmlDescriptor.set.call(template, html)",
        'Object.defineProperty(Element.prototype, "innerHTML"',
        'compact.startsWith("javascript:")',
        'compact.startsWith("data:")',
        'compact.startsWith("vbscript:")',
    ):
        assert_true(required in script, f"Missing front-end safety guard: {required}")

    unsafe_href = unsafe_dynamic_url_lines(script, "href")
    unsafe_src = unsafe_dynamic_url_lines(script, "src")
    assert_true(not unsafe_href, "Dynamic href must use safeUrl(): " + "; ".join(unsafe_href[:5]))
    assert_true(not unsafe_src, "Dynamic src must use safeUrl(): " + "; ".join(unsafe_src[:5]))


def check_api_error_sanitization() -> None:
    source = read_text("app.py")
    cache_source = read_text("cache.py")
    forbidden = (
        "{exc}",
        "str(exc)",
        'cache_data["last_error"] = str(exc)',
    )
    for token in forbidden:
        assert_true(token not in source, f"Raw exception detail may leak through API payloads: {token}")
        assert_true(token not in cache_source, f"Raw exception detail may leak through API payloads: {token}")
    for required in (
        "PUBLIC_DATA_SOURCE_ERROR_MESSAGE",
        "def api_exception_response",
        "LOGGER.exception",
    ):
        assert_true(required in source, f"Missing API error guard: {required}")
    assert_true("PUBLIC_CACHE_ERROR_MESSAGE" in cache_source, "Missing API error guard: PUBLIC_CACHE_ERROR_MESSAGE")


def check_admin_token_guard() -> None:
    app_source = read_text("app.py")
    security_source = read_text("security.py")
    assert_true("DERIVATIVES_ADMIN_TOKEN" in security_source, "Admin token must come from environment")
    assert_true("hmac.compare_digest" in security_source, "Admin token comparison must use constant-time compare")
    assert_true('request.args.get("admin_token")' not in app_source and 'request.args.get("admin_token")' not in security_source, "Admin token must not be accepted in query string")
    assert_true('request.values.get("admin_token")' not in app_source and 'request.values.get("admin_token")' not in security_source, "Admin token must not be accepted from request values")


def check_security_headers_static() -> None:
    source = read_text("security.py")
    for header in (
        "X-Content-Type-Options",
        "X-Frame-Options",
        "Referrer-Policy",
        "Permissions-Policy",
        "Content-Security-Policy",
        "Strict-Transport-Security",
    ):
        assert_true(header in source, f"Missing security header: {header}")
    for directive in ("default-src 'self'", "base-uri 'self'", "frame-ancestors 'none'", "connect-src 'self'"):
        assert_true(directive in source, f"Missing CSP directive: {directive}")


def check_static_whitelist_static() -> None:
    app_source = read_text("app.py")
    config_source = read_text("market_config.py")
    for required in ("ROOT_STATIC_FILES", "ASSET_STATIC_FILES", "send_from_directory"):
        assert_true(required in app_source or required in config_source, f"Missing static whitelist control: {required}")
    forbidden_entries = (".py", ".sqlite", ".sqlite3", ".db", ".env", ".docx")
    whitelist_section = "\n".join(
        line for line in config_source.splitlines()
        if "ROOT_STATIC_FILES" in line or "ASSET_STATIC_FILES" in line or line.strip().startswith('"')
    )
    for suffix in forbidden_entries:
        assert_true(suffix not in whitelist_section, f"Static whitelist must not include sensitive suffix: {suffix}")


def check_rate_limit_static() -> None:
    app_source = read_text("app.py")
    security_source = read_text("security.py")
    for required in (
        "API_RATE_LIMIT_PER_WINDOW",
        "API_RATE_LIMIT_WINDOW_SECONDS",
        "cleanup_api_rate_limit_state",
        "RATE_LIMITED",
        "Retry-After",
    ):
        assert_true(required in security_source, f"Missing rate-limit guard: {required}")
    assert_true("ProxyFix" in app_source, "Missing rate-limit guard: ProxyFix")
    assert_true('request.headers.get("X-Forwarded-For")' not in security_source, "Rate limit must not trust X-Forwarded-For directly")


def check_environment_and_persistence_static() -> None:
    app_source = read_text("app.py")
    security_source = read_text("security.py")
    store_source = read_text("derivatives_store.py")
    assert_true('os.environ.get("DERIVATIVES_DB_PATH"' in app_source, "Database path must be configurable by environment")
    assert_true('os.environ.get("DERIVATIVES_ADMIN_TOKEN")' in security_source, "Admin token must be configured by environment")
    assert_true("self.path.parent.mkdir(parents=True, exist_ok=True)" in store_source, "DB directory must be created for portable persistence")
    assert_true("PRAGMA journal_mode = WAL" in store_source, "SQLite WAL mode must be enabled")
    assert_true("_PRUNE_ALLOWLIST" in store_source, "Dynamic prune SQL must use an allowlist")


def call_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        base = call_name(ast.Call(func=func.value, args=[], keywords=[])) if isinstance(func.value, ast.Call) else ""
        if isinstance(func.value, ast.Name):
            base = func.value.id
        return f"{base}.{func.attr}" if base else func.attr
    return ""


def function_name_stack(tree: ast.AST) -> dict[ast.AST, str]:
    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent

    names: dict[ast.AST, str] = {}
    for node in ast.walk(tree):
        current = node
        function_name = ""
        while current in parents:
            current = parents[current]
            if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
                function_name = current.name
                break
        names[node] = function_name
    return names


def check_sql_parameterization() -> None:
    for filename in ("app.py", "derivatives_store.py"):
        source = read_text(filename)
        tree = ast.parse(source, filename=filename)
        function_names = function_name_stack(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = call_name(node)
            if not (name.endswith(".execute") or name.endswith(".executemany")):
                continue
            if not node.args:
                continue
            first_arg = node.args[0]
            if isinstance(first_arg, ast.JoinedStr):
                function_name = function_names.get(node, "")
                assert_true(
                    filename == "derivatives_store.py" and function_name == "_prune_to_limit",
                    f"{filename}:{node.lineno} SQL f-string is not allowed outside allowlisted pruning",
                )
            if isinstance(first_arg, ast.BinOp):
                raise GuardrailFailure(f"{filename}:{node.lineno} SQL string concatenation/interpolation is not allowed")
    store_source = read_text("derivatives_store.py")
    assert_true("if (table, where_field) not in DerivativesStore._PRUNE_ALLOWLIST" in store_source, "Dynamic prune SQL must validate table/field allowlist")


def check_dangerous_functions() -> None:
    python_forbidden = {"eval", "exec", "os.system", "os.popen", "pickle.loads", "pickle.load"}
    for filename in ("app.py", "security.py", "cache.py", "derivatives_store.py", "market_config.py"):
        tree = ast.parse(read_text(filename), filename=filename)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = call_name(node)
                assert_true(name not in python_forbidden, f"{filename}:{node.lineno} dangerous function is forbidden: {name}")
                if name in {"subprocess.run", "subprocess.call", "subprocess.Popen"}:
                    for keyword in node.keywords:
                        if keyword.arg == "shell" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True:
                            raise GuardrailFailure(f"{filename}:{node.lineno} subprocess shell=True is forbidden")

    js_source = read_text("app.js")
    js_forbidden_patterns = {
        r"\beval\s*\(": "eval()",
        r"\bnew\s+Function\b": "new Function",
        r"\bdocument\.write\s*\(": "document.write()",
    }
    for pattern, label in js_forbidden_patterns.items():
        assert_true(not re.search(pattern, js_source), f"JavaScript dangerous function is forbidden: {label}")


def check_hardcoded_secrets() -> None:
    candidates = ["app.py", "security.py", "cache.py", "market_config.py", "derivatives_store.py", "app.js", "derivatives-ui.js"]
    secret_assignment = re.compile(
        r"(?i)\b(api[_-]?key|secret|password|token)\b\s*[:=]\s*['\"]([^'\"]{8,})['\"]"
    )
    allowed_fragments = (
        "DERIVATIVES_ADMIN_TOKEN",
        "X-Admin-Token",
        "X-Derivatives-Admin-Token",
        "ADMIN_AUTH_REQUIRED",
        "test-admin-token",
    )
    for filename in candidates:
        source = read_text(filename)
        for match in secret_assignment.finditer(source):
            line = source[max(0, match.start() - 120):match.end() + 120]
            assert_true(
                any(fragment in line for fragment in allowed_fragments),
                f"{filename} appears to contain a hardcoded secret assignment near: {match.group(1)}",
            )


def load_app_with_temp_db() -> tuple[Any, tempfile.TemporaryDirectory[str]]:
    tempdir = tempfile.TemporaryDirectory(prefix="market-pulse-guardrail-")
    os.environ["MARKET_PULSE_DISABLE_BACKGROUND"] = "1"
    os.environ["MARKET_PULSE_LOG_LEVEL"] = "CRITICAL"
    os.environ["DERIVATIVES_ADMIN_TOKEN"] = "guardrail-admin-token"
    os.environ["DERIVATIVES_DB_PATH"] = str(Path(tempdir.name) / "guardrail.sqlite3")
    if "app" in sys.modules:
        del sys.modules["app"]
    app_module = importlib.import_module("app")
    return app_module, tempdir


def check_runtime_security_behaviour() -> None:
    app_module, tempdir = load_app_with_temp_db()
    security_module = importlib.import_module("security")
    try:
        client = app_module.app.test_client()

        for path, expected_status in (
            ("/app.js", 200),
            ("/assets/app-icon.svg", 200),
            ("/app.py", 404),
            ("/derivatives-platform.sqlite3", 404),
            ("/assets/app.py", 404),
            ("/V1.0_Security_Baseline_Guardrail_Specification.docx", 404),
        ):
            response = client.get(path)
            assert_true(response.status_code == expected_status, f"{path} expected {expected_status}, got {response.status_code}")

        health = client.get("/api/health")
        headers = health.headers
        assert_true(headers.get("X-Content-Type-Options") == "nosniff", "Missing nosniff header at runtime")
        assert_true(headers.get("X-Frame-Options") == "DENY", "Missing DENY frame header at runtime")
        assert_true("frame-ancestors 'none'" in headers.get("Content-Security-Policy", ""), "CSP frame-ancestors missing at runtime")

        payload = {"rows": [{"institution": "guardrail", "product_code": "TX_GUARD", "trade_date": "2026-06-23"}]}
        denied = client.post("/api/institution/import", json=payload)
        assert_true(denied.status_code == 403, "Admin import without header token must be denied")
        query_denied = client.post("/api/institution/import?admin_token=guardrail-admin-token", json=payload)
        assert_true(query_denied.status_code == 403, "Admin token in URL query must be denied")
        imported = client.post("/api/institution/import", json=payload, headers={"X-Admin-Token": "guardrail-admin-token"})
        assert_true(imported.status_code == 200, f"Admin header token should be accepted, got {imported.status_code}")

        original_limit = security_module.API_RATE_LIMIT_PER_WINDOW
        security_module.API_RATE_LIMIT_PER_WINDOW = 2
        try:
            with security_module.API_RATE_LIMIT_LOCK:
                security_module.API_RATE_LIMIT_STATE.clear()
            assert_true(client.get("/api/derivatives/v1-status", headers={"X-Forwarded-For": "203.0.113.1"}).status_code == 200, "Rate limit first request failed")
            assert_true(client.get("/api/derivatives/v1-status", headers={"X-Forwarded-For": "203.0.113.2"}).status_code == 200, "Rate limit second request failed")
            limited = client.get("/api/derivatives/v1-status", headers={"X-Forwarded-For": "203.0.113.3"})
            assert_true(limited.status_code == 429, "Rate limit must ignore spoofed X-Forwarded-For and return 429")
            assert_true("Retry-After" in limited.headers, "Rate limit response must include Retry-After")
        finally:
            security_module.API_RATE_LIMIT_PER_WINDOW = original_limit
            with security_module.API_RATE_LIMIT_LOCK:
                security_module.API_RATE_LIMIT_STATE.clear()

        db_path = Path(os.environ["DERIVATIVES_DB_PATH"])
        assert_true(db_path.exists(), "Guardrail temp database was not created")
    finally:
        tempdir.cleanup()


CHECKS = (
    ("S-01 static whitelist", check_static_whitelist_static),
    ("S-02 admin header token", check_admin_token_guard),
    ("S-03 SQL parameterization", check_sql_parameterization),
    ("S-04/S-05 XSS and URL safety", check_frontend_xss_and_url_safety),
    ("S-06 API error sanitization", check_api_error_sanitization),
    ("S-07 rate limiting", check_rate_limit_static),
    ("S-08 security headers", check_security_headers_static),
    ("S-09/S-10 env and persistence", check_environment_and_persistence_static),
    ("Dangerous functions", check_dangerous_functions),
    ("Hardcoded secrets", check_hardcoded_secrets),
    ("Runtime security behaviour", check_runtime_security_behaviour),
)


def run_checks() -> list[CheckResult]:
    results: list[CheckResult] = []
    for name, check in CHECKS:
        try:
            check()
        except Exception as exc:  # noqa: BLE001
            results.append(CheckResult(name, False, str(exc)))
        else:
            results.append(CheckResult(name, True))
    return results


def main() -> int:
    results = run_checks()
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        detail = f" - {result.detail}" if result.detail else ""
        print(f"[{status}] {result.name}{detail}")
    failed = [result for result in results if not result.passed]
    if failed:
        print(f"SECURITY_GUARDRAIL_FAILED: {len(failed)} check(s) failed")
        return 1
    print("SECURITY_GUARDRAIL_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
