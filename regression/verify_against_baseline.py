"""工單 00 第三、四部分:與行為基準比對,判斷現版是否偏離原版行為。

用法:
    python regression/verify_against_baseline.py --quick   # API 比對 + 安全檢查(約 1 分鐘)
    python regression/verify_against_baseline.py --full    # quick + Playwright 前端比對

任一檢查失敗則結束碼為 1(可被 Stop hook 或 CI 使用)。
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from capture_baseline import build_cases, fetch  # noqa: E402
from diffing import apply_mask, deep_diff, extract_schema, schema_diff  # noqa: E402
from route_scan import api_get_routes  # noqa: E402
from server_harness import start_server  # noqa: E402

REGRESSION_DIR = Path(__file__).resolve().parent
REPO_ROOT = REGRESSION_DIR.parent
BASELINE_DIR = REGRESSION_DIR / "baseline"
API_BASELINE_DIR = BASELINE_DIR / "api"
MANIFEST_PATH = BASELINE_DIR / "manifest.json"
SECURITY_HEADERS_PATH = BASELINE_DIR / "security_headers.json"
ESCAPEHTML_BASELINE_PATH = BASELINE_DIR / "escapehtml_baseline.json"
APP_JS_PATH = REPO_ROOT / "app.js"

RETRY_DELAY_SECONDS = 3


class CheckReport:
    def __init__(self, name: str):
        self.name = name
        self.ok = True
        self.details: list[str] = []

    def fail(self, message: str) -> None:
        self.ok = False
        self.details.append(message)

    def print_result(self) -> None:
        print(f"[{'PASS' if self.ok else 'FAIL'}] {self.name}")
        for detail in self.details:
            print(f"    - {detail}")


def check_security_guardrail() -> CheckReport:
    """工單 00 第三部分第 1、2 點:security_guardrail_check.py 內含 SQL 參數化靜態掃描。"""
    report = CheckReport("security_guardrail_check.py")
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "security_guardrail_check.py")],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        report.fail(proc.stdout.strip() or proc.stderr.strip())
    return report


def check_escapehtml_threshold() -> CheckReport:
    """工單 00 第三部分第 3 點:escapeHtml 呼叫次數不得低於基準值的 95%。"""
    report = CheckReport("app.js escapeHtml() 呼叫次數 >= 基準 95%")
    if not ESCAPEHTML_BASELINE_PATH.exists():
        report.fail(f"找不到基準檔 {ESCAPEHTML_BASELINE_PATH}")
        return report
    baseline = json.loads(ESCAPEHTML_BASELINE_PATH.read_text(encoding="utf-8"))
    baseline_count = baseline["escapeHtml_call_count"]
    threshold = baseline_count * baseline.get("threshold_pct", 95) / 100.0
    current_count = len(re.findall(r"escapeHtml\(", APP_JS_PATH.read_text(encoding="utf-8")))
    if current_count < threshold:
        report.fail(f"現況 {current_count} 次 < 門檻 {threshold:.0f} 次(基準 {baseline_count} 次的 95%)")
    else:
        report.details.append(f"現況 {current_count} 次(基準 {baseline_count} 次)")
    return report


def check_security_headers() -> CheckReport:
    """工單 00 第三部分第 4 點:CSP、X-Frame-Options、HSTS 等安全標頭必須與基準完全一致。"""
    report = CheckReport("回應安全標頭與基準一致")
    if not SECURITY_HEADERS_PATH.exists():
        report.fail(f"找不到基準檔 {SECURITY_HEADERS_PATH}")
        return report
    baseline_headers = json.loads(SECURITY_HEADERS_PATH.read_text(encoding="utf-8"))
    with start_server() as server:
        import urllib.request

        req = urllib.request.Request(server.base_url + "/api/health", headers={"User-Agent": "regression-verify"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            current_headers = {name: resp.headers.get(name) for name in baseline_headers}
    for name, expected in baseline_headers.items():
        actual = current_headers.get(name)
        if actual != expected:
            report.fail(f"{name}: 基準={expected!r} 現況={actual!r}")
    return report


def _check_one_endpoint(server_base_url: str, endpoint: dict) -> str | None:
    """回傳 None 表示通過,否則回傳失敗描述。"""
    from capture_baseline import Case

    # endpoint["request_path"] 已含 query string,整段當 url_path 即可,query 留空。
    case = Case(name=endpoint["name"], rule=endpoint["rule"], url_path=endpoint["request_path"], query={})
    status, _content_type, body = fetch(server_base_url, case)
    baseline_file = BASELINE_DIR / endpoint["baseline_file"]
    stored_value = json.loads(baseline_file.read_text(encoding="utf-8"))

    if endpoint["structure_only"]:
        current_schema = extract_schema(body)
        schema_diffs = schema_diff(stored_value, current_schema)
        if schema_diffs:
            return f"{endpoint['request_path']}: 回應結構(schema)與基準不同 - {'; '.join(schema_diffs[:5])}"
        return None

    if status != endpoint["status_code"]:
        return f"{endpoint['request_path']}: 狀態碼基準={endpoint['status_code']} 現況={status}"

    masked_current = apply_mask(body, _parse_mask_paths(endpoint["mask_paths"]))
    diffs = deep_diff(stored_value, masked_current)
    if diffs:
        return f"{endpoint['request_path']}: {'; '.join(diffs[:5])}"
    return None


def _parse_mask_paths(mask_path_strs: list[str]) -> list[tuple]:
    """把 manifest 裡的 '$', 'a.b[0].c' 這類字串路徑轉回 apply_mask 需要的 tuple 路徑。"""
    parsed: list[tuple] = []
    token_re = re.compile(r"\[(\d+)\]|\.?([^.\[\]]+)")
    for path_str in mask_path_strs:
        if path_str == "$":
            parsed.append(())
            continue
        parts: list = []
        for match in token_re.finditer(path_str):
            if match.group(1) is not None:
                parts.append(int(match.group(1)))
            elif match.group(2):
                parts.append(match.group(2))
        parsed.append(tuple(parts))
    return parsed


def check_api_baseline() -> CheckReport:
    """工單 00 第一部分:API 回應行為必須與基準一致(含遮罩時變欄位、structure-only 端點)。"""
    report = CheckReport("API 行為基準比對")
    if not MANIFEST_PATH.exists():
        report.fail(f"找不到基準 manifest {MANIFEST_PATH},請先執行 capture_baseline.py")
        return report

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    endpoints = manifest["endpoints"]

    with start_server() as server:
        pending = {ep["name"]: ep for ep in endpoints}
        first_pass_failures: dict[str, str] = {}
        for name, endpoint in pending.items():
            failure = _check_one_endpoint(server.base_url, endpoint)
            if failure:
                first_pass_failures[name] = failure

        if first_pass_failures:
            # 外部資料源當機造成的 fail,重跑一次確認;連續 fail 才視為真錯誤。
            print(f"  [verify] {len(first_pass_failures)} 個端點第一次比對失敗,{RETRY_DELAY_SECONDS} 秒後重試...")
            time.sleep(RETRY_DELAY_SECONDS)
            for name in list(first_pass_failures.keys()):
                endpoint = pending[name]
                failure = _check_one_endpoint(server.base_url, endpoint)
                if failure is None:
                    del first_pass_failures[name]
                else:
                    first_pass_failures[name] = failure

    for failure in first_pass_failures.values():
        report.fail(failure)
    return report


def run_frontend_compare() -> CheckReport:
    """工單 00 第四部分:--full 模式時執行 Playwright 前端比對。"""
    report = CheckReport("frontend_check.py --compare")
    proc = subprocess.run(
        [sys.executable, str(REGRESSION_DIR / "frontend_check.py"), "--compare"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        report.fail(proc.stdout.strip() or proc.stderr.strip())
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--quick", action="store_true", help="API 比對 + 安全檢查")
    group.add_argument("--full", action="store_true", help="quick + Playwright 前端比對")
    args = parser.parse_args()

    reports = [
        check_security_guardrail(),
        check_escapehtml_threshold(),
        check_security_headers(),
        check_api_baseline(),
    ]
    if args.full:
        reports.append(run_frontend_compare())

    for report in reports:
        report.print_result()

    ok = all(report.ok for report in reports)
    print(f"\n{'VERIFY_OK' if ok else 'VERIFY_FAILED'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
