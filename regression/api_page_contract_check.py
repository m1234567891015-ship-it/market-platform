"""Phase 1/2:驗證 21 個頁面的 API 導入與回應契約。

用法:
    python regression/api_page_contract_check.py

Phase 1 驗證 API path 是否符合 regression/page_api_manifest.json:
- 21 個 HTML 頁面必須各有一筆 manifest。
- initial 必須出現在該頁面的 page-load HAR。
- interactive 必須出現在該頁面 interaction HAR 相對於 initial 新增的 path。
- HAR 中出現未登錄的 API path 時失敗。

Phase 2 額外驗證 HTTP 結果分類與 API schema manifest。HAR 是既有 frozen fixture，
本檢查不會打外部網路。
"""
from __future__ import annotations

import argparse
import base64
import fnmatch
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


REGRESSION_DIR = Path(__file__).resolve().parent
REPO_ROOT = REGRESSION_DIR.parent
MANIFEST_PATH = REGRESSION_DIR / "page_api_manifest.json"
SCHEMA_MANIFEST_PATH = REGRESSION_DIR / "api_schema_manifest.json"
INITIAL_HAR_DIR = REGRESSION_DIR / "baseline" / "har"
INTERACTION_HAR_DIR = REGRESSION_DIR / "baseline" / "interactions" / "har"


class ContractError(Exception):
    """Raised when the page API manifest or observed HAR violates the contract."""


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ContractError(f"找不到檔案: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ContractError(f"JSON 格式錯誤: {path}: {exc}") from exc


def _decode_har_body(entry: dict, path: Path) -> tuple[Any | None, str | None]:
    content = entry.get("response", {}).get("content", {})
    text = content.get("text")
    if text in (None, ""):
        return None, None
    if content.get("encoding") == "base64":
        try:
            text = base64.b64decode(text).decode("utf-8")
        except (ValueError, UnicodeDecodeError) as exc:
            return None, f"HAR response base64 解碼失敗: {exc}"
    try:
        return json.loads(text), None
    except json.JSONDecodeError as exc:
        return None, f"HAR response JSON 解析失敗: {exc}"


def _api_entries_from_har(path: Path) -> list[dict[str, Any]]:
    payload = _load_json(path)
    try:
        entries = payload["log"]["entries"]
    except (KeyError, TypeError) as exc:
        raise ContractError(f"HAR 結構缺少 log.entries: {path}") from exc

    api_entries: list[dict[str, Any]] = []
    for entry in entries:
        try:
            request = entry["request"]
            url = request["url"]
        except (KeyError, TypeError) as exc:
            raise ContractError(f"HAR entry 缺少 request.url: {path}") from exc
        parsed = urlsplit(url)
        if parsed.path.startswith("/api/"):
            response = entry.get("response", {})
            try:
                status = int(response.get("status", 0))
            except (TypeError, ValueError):
                status = 0
            body, body_error = _decode_har_body(entry, path)
            api_entries.append(
                {
                    "path": parsed.path,
                    "status": status,
                    "body": body,
                    "body_error": body_error,
                    "url": url,
                }
            )
    return api_entries


def _api_paths_from_har(path: Path) -> set[str]:
    return {entry["path"] for entry in _api_entries_from_har(path)}


def _validate_path_list(page_file: str, field: str, values: object) -> set[str]:
    if not isinstance(values, list):
        raise ContractError(f"{page_file}.{field} 必須是陣列")
    normalized: set[str] = set()
    for value in values:
        if not isinstance(value, str) or not value.startswith("/api/"):
            raise ContractError(f"{page_file}.{field} 含非法 API path: {value!r}")
        if "?" in value or "#" in value:
            raise ContractError(
                f"{page_file}.{field} Phase 1 只接受 path，不接受 query/hash: {value!r}"
            )
        if value in normalized:
            raise ContractError(f"{page_file}.{field} 有重複 API path: {value}")
        normalized.add(value)
    return normalized


def _validate_manifest(manifest: dict) -> dict[str, dict[str, set[str]]]:
    if manifest.get("schema_version") != 1:
        raise ContractError("page API manifest schema_version 必須為 1")
    if manifest.get("match_mode") != "path":
        raise ContractError("Phase 1 的 match_mode 必須為 path")

    pages = manifest.get("pages")
    if not isinstance(pages, list):
        raise ContractError("page API manifest.pages 必須是陣列")

    result: dict[str, dict[str, set[str]]] = {}
    for page in pages:
        if not isinstance(page, dict):
            raise ContractError(f"pages 含非 object 項目: {page!r}")
        file = page.get("file")
        if not isinstance(file, str) or not file.endswith(".html"):
            raise ContractError(f"page file 非法: {file!r}")
        if file in result:
            raise ContractError(f"manifest page 重複: {file}")
        initial = _validate_path_list(file, "initial", page.get("initial"))
        interactive = _validate_path_list(file, "interactive", page.get("interactive"))
        overlap = initial & interactive
        if overlap:
            raise ContractError(
                f"{file} 同一 API path 不可同時列在 initial 與 interactive: "
                + ", ".join(sorted(overlap))
            )
        result[file] = {"initial": initial, "interactive": interactive}
    return result


_ALLOWED_SCHEMA_TYPES = {"array", "boolean", "integer", "null", "number", "object", "string"}


def _validate_schema_path(path: str, field_name: str) -> None:
    if not isinstance(path, str) or not path:
        raise ContractError(f"schema {field_name} 含非法 path: {path!r}")
    if any(token in path for token in ("[", "]", "*", "?")):
        raise ContractError(f"schema {field_name} 目前只接受 dot path: {path!r}")


def _validate_schema_manifest(manifest: dict) -> list[dict[str, Any]]:
    if manifest.get("schema_version") != 1:
        raise ContractError("api schema manifest schema_version 必須為 1")
    if manifest.get("match_mode") != "fnmatch_path":
        raise ContractError("api schema manifest match_mode 必須為 fnmatch_path")
    endpoints = manifest.get("endpoints")
    if not isinstance(endpoints, list) or not endpoints:
        raise ContractError("api schema manifest.endpoints 必須是非空陣列")

    allowed_types = set(manifest.get("type_names", []))
    if allowed_types != _ALLOWED_SCHEMA_TYPES:
        raise ContractError("api schema manifest.type_names 與實作支援型別不一致")

    result: list[dict[str, Any]] = []
    seen_patterns: set[str] = set()
    for endpoint in endpoints:
        if not isinstance(endpoint, dict):
            raise ContractError(f"schema endpoints 含非 object 項目: {endpoint!r}")
        pattern = endpoint.get("path_pattern")
        if not isinstance(pattern, str) or not pattern.startswith("/api/"):
            raise ContractError(f"schema path_pattern 非法: {pattern!r}")
        if pattern in seen_patterns:
            raise ContractError(f"schema path_pattern 重複: {pattern}")
        seen_patterns.add(pattern)
        required_paths = endpoint.get("required_paths")
        if not isinstance(required_paths, list):
            raise ContractError(f"{pattern}.required_paths 必須是陣列")
        for required_path in required_paths:
            _validate_schema_path(required_path, f"{pattern}.required_paths")
        types = endpoint.get("types", {})
        if not isinstance(types, dict):
            raise ContractError(f"{pattern}.types 必須是 object")
        for required_path, type_name in types.items():
            _validate_schema_path(required_path, f"{pattern}.types")
            if required_path not in required_paths:
                raise ContractError(f"{pattern}.types 的 path 未列在 required_paths: {required_path}")
            if type_name not in allowed_types:
                raise ContractError(f"{pattern}.types 含不支援型別: {type_name!r}")
        result.append(
            {
                "path_pattern": pattern,
                "required_paths": tuple(required_paths),
                "types": dict(types),
            }
        )
    return result


def _validate_background_failures(
    manifest: dict,
    page_files: set[str],
) -> dict[tuple[str, str], set[int]]:
    entries = manifest.get("expected_background_failures", [])
    if not isinstance(entries, list):
        raise ContractError("page API manifest.expected_background_failures 必須是陣列")
    result: dict[tuple[str, str], set[int]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ContractError(f"expected_background_failures 含非 object 項目: {entry!r}")
        page = entry.get("page")
        path = entry.get("path")
        statuses = entry.get("status_codes")
        if page not in page_files:
            raise ContractError(f"背景失敗政策指向未登錄頁面: {page!r}")
        if not isinstance(path, str) or not path.startswith("/api/") or "?" in path:
            raise ContractError(f"背景失敗政策 path 非法: {path!r}")
        if not isinstance(statuses, list) or not statuses or any(not isinstance(status, int) for status in statuses):
            raise ContractError(f"{page}:{path} status_codes 必須是非空整數陣列")
        key = (page, path)
        if key in result:
            raise ContractError(f"背景失敗政策重複: {page}:{path}")
        result[key] = set(statuses)
    return result


def _schema_for_path(path: str, schema_contract: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates = [
        endpoint
        for endpoint in schema_contract
        if fnmatch.fnmatchcase(path, endpoint["path_pattern"])
    ]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda endpoint: sum(char not in "*?" for char in endpoint["path_pattern"]),
    )


def _value_at_path(value: Any, path: str) -> tuple[bool, Any]:
    current = value
    for segment in path.split("."):
        if not isinstance(current, dict) or segment not in current:
            return False, None
        current = current[segment]
    return True, current


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _schema_errors(path: str, entry: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    body = entry["body"]
    if entry["body_error"]:
        return [f"{path}: {entry['body_error']}"]
    if body is None:
        return [f"{path}: HTTP {entry['status']} success response 沒有 JSON body"]

    errors: list[str] = []
    for required_path in schema["required_paths"]:
        exists, _value = _value_at_path(body, required_path)
        if not exists:
            errors.append(f"{path}: 缺少必要欄位 {required_path}")
    for type_path, expected_type in schema["types"].items():
        exists, actual_value = _value_at_path(body, type_path)
        if exists and _type_name(actual_value) != expected_type:
            errors.append(
                f"{path}: 欄位 {type_path} 型別 {expected_type} -> {_type_name(actual_value)}"
            )
    return errors


def _is_external_failure(status: int, body: Any) -> bool:
    if status == 0:
        return True
    return (
        status in {502, 503, 504}
        and isinstance(body, dict)
        and body.get("success") is False
        and bool(body.get("error_code"))
    )


def _classify_entry(
    page: str,
    entry: dict[str, Any],
    expected_background_failures: dict[tuple[str, str], set[int]],
) -> str:
    key = (page, entry["path"])
    if entry["status"] in expected_background_failures.get(key, set()):
        return "expected_background_failure"
    if _is_external_failure(entry["status"], entry["body"]):
        return "external_failure"
    if 200 <= entry["status"] < 300:
        return "success"
    return "unexpected_http_error"


def check_contract(
    manifest_path: Path = MANIFEST_PATH,
    schema_manifest_path: Path = SCHEMA_MANIFEST_PATH,
) -> tuple[list[str], list[str]]:
    """Return (errors, summary_lines) without changing files or starting a server."""
    errors: list[str] = []
    summary: list[str] = []
    try:
        manifest = _load_json(manifest_path)
        expected = _validate_manifest(manifest)
        expected_background_failures = _validate_background_failures(manifest, set(expected))
        schema_contract = _validate_schema_manifest(_load_json(schema_manifest_path))
    except ContractError as exc:
        return [str(exc)], summary

    actual_pages = {path.name for path in REPO_ROOT.glob("*.html")}
    manifest_pages = set(expected)
    missing_manifest = sorted(actual_pages - manifest_pages)
    extra_manifest = sorted(manifest_pages - actual_pages)
    if missing_manifest:
        errors.append("HTML 頁面未登錄: " + ", ".join(missing_manifest))
    if extra_manifest:
        errors.append("manifest 登錄了不存在的 HTML: " + ", ".join(extra_manifest))

    if len(actual_pages) != 21:
        errors.append(f"目前 HTML 頁面數量為 {len(actual_pages)}，預期為 21")
    if len(manifest_pages) != 21:
        errors.append(f"manifest 頁面數量為 {len(manifest_pages)}，預期為 21")

    checked_pages = sorted(actual_pages & manifest_pages)
    classification_totals = {
        "success": 0,
        "expected_background_failure": 0,
        "external_failure": 0,
        "unexpected_http_error": 0,
        "schema_failure": 0,
    }
    for file in checked_pages:
        initial_har = INITIAL_HAR_DIR / f"{file}.har"
        interaction_har = INTERACTION_HAR_DIR / f"{file}.har"
        if not initial_har.exists():
            errors.append(f"{file}: 找不到 page-load HAR {initial_har}")
            continue
        if not interaction_har.exists():
            errors.append(f"{file}: 找不到 interaction HAR {interaction_har}")
            continue

        try:
            initial_entries = _api_entries_from_har(initial_har)
            interaction_entries = _api_entries_from_har(interaction_har)
        except ContractError as exc:
            errors.append(f"{file}: {exc}")
            continue

        observed_initial = {entry["path"] for entry in initial_entries}
        observed_interaction = {entry["path"] for entry in interaction_entries}
        observed_interactive = observed_interaction - observed_initial
        expected_initial = expected[file]["initial"]
        expected_interactive = expected[file]["interactive"]

        missing_initial = sorted(expected_initial - observed_initial)
        extra_initial = sorted(observed_initial - expected_initial)
        missing_interactive = sorted(expected_interactive - observed_interactive)
        extra_interactive = sorted(observed_interactive - expected_interactive)

        if missing_initial:
            errors.append(f"{file}: initial 缺少 " + ", ".join(missing_initial))
        if extra_initial:
            errors.append(f"{file}: initial 未登錄 " + ", ".join(extra_initial))
        if missing_interactive:
            errors.append(f"{file}: interactive 缺少 " + ", ".join(missing_interactive))
        if extra_interactive:
            errors.append(f"{file}: interactive 未登錄 " + ", ".join(extra_interactive))

        classification_counts = {key: 0 for key in classification_totals}
        for entry in initial_entries + interaction_entries:
            category = _classify_entry(file, entry, expected_background_failures)
            if category == "success":
                schema = _schema_for_path(entry["path"], schema_contract)
                if schema is None:
                    category = "schema_failure"
                    errors.append(f"{file}: {entry['path']} 沒有 schema contract")
                else:
                    schema_errors = _schema_errors(entry["path"], entry, schema)
                    if schema_errors:
                        category = "schema_failure"
                        errors.extend(f"{file}: {error}" for error in schema_errors)
            elif category == "unexpected_http_error":
                errors.append(
                    f"{file}: {entry['path']} 未預期 HTTP status={entry['status']}"
                )
            classification_counts[category] += 1
            classification_totals[category] += 1

        summary.append(
            f"{file}: initial={len(observed_initial)}, "
            f"interactive_new={len(observed_interactive)}, status="
            + ", ".join(
                f"{key}={classification_counts[key]}"
                for key in classification_counts
                if classification_counts[key]
            )
        )

    summary.append(
        "total status="
        + ", ".join(
            f"{key}={classification_totals[key]}"
            for key in classification_totals
            if classification_totals[key]
        )
    )
    return errors, summary


def main() -> int:
    parser = argparse.ArgumentParser(description="檢查 21 頁 API 導入、錯誤分類與 schema contract")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=MANIFEST_PATH,
        help=f"API manifest 路徑（預設: {MANIFEST_PATH}）",
    )
    parser.add_argument(
        "--schema-manifest",
        type=Path,
        default=SCHEMA_MANIFEST_PATH,
        help=f"schema manifest 路徑（預設: {SCHEMA_MANIFEST_PATH}）",
    )
    args = parser.parse_args()

    errors, summary = check_contract(args.manifest, args.schema_manifest)
    if errors:
        print("[FAIL] API page contract")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("[PASS] API page contract: 21/21 頁")
    for line in summary:
        print(f"  {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
