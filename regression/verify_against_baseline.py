"""工單 00 第三、四部分:與行為基準比對,判斷現版是否偏離原版行為。

用法:
    python regression/verify_against_baseline.py --quick        # offline fixture API 比對 + 安全檢查(快、穩定)
    python regression/verify_against_baseline.py --quick --api-live  # + 即時端點(見下)
    python regression/verify_against_baseline.py --full         # quick + --api-live + Playwright 前端比對 + 互動比對

TD-17/TD-19:`--quick` 只用 `regression/baseline` 的 loopback fixture
比對快取型端點,不啟動正式 app、不打外部資料源,因此在禁止外網時仍可
重現 API schema/value 驗證。`live-sectors`/`live-overview`/`live-stocks`/
`live-search` 這類設計上無快取、每次直接打外部資料源的端點,移到獨立的
`--api-live` 旗標,`--full` 自動包含,`--quick` 預設不含,兩者分工明確。

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
from offline_fixtures import OfflineFixtureServer  # noqa: E402
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

# TD-17:這 4 個端點的 handler(routes_twse.py)設計上永遠直接呼叫外部即時
# 抓取函式,沒有 cache_data/ensure_cache() 這層快取可暖身,天生比其餘端點
# 更容易受外部資料源當下延遲影響。獨立移到 --api-live,不讓它們拖累
# --quick 的穩定性,--full 仍然涵蓋(見 check_api_live_baseline)。
ALWAYS_LIVE_ENDPOINT_NAMES = {
    "api__twse__live-sectors",
    "api__twse__live-overview",
    "api__twse__live-stocks",
    "api__twse__live-search",
}

# TD-19:每個 manifest endpoint 都有一筆政策；required paths 只檢查 key 是否存在，
# 不把 null/空資料誤判為失敗。error-only endpoint 由 ERROR_ONLY_ENDPOINT_NAMES
# 標記，等 healthy fixture 補齊後才轉成 success policy。
REQUIRED_KEY_PATHS: dict[str, tuple[str, ...]] = {
    "api__health": ("status",),
    "api__twse__site-data": ("snapshotDate", "stockCount", "sectors"),
    "api__twse__live-sectors": ("snapshotDate", "sectors"),
    "api__twse__live-overview": ("snapshotDate", "marketOverview", "marketStats", "stocks"),
    "api__twse__live-stocks": ("snapshotDate", "count", "stocks"),
    "api__twse__live-search": ("query", "count", "results"),
    "api__yahoo__sector": (),
    "api__yahoo__sector-chart": (),
    "api__market__penny-sector-recommendations": ("available", "markets"),
    "api__market__international-indexes": ("count", "indexes"),
    "api__global-market__us-stocks": ("category", "items", "summary"),
    "api__twse__search": ("query", "count", "results"),
    "api__twse__stock__2330": ("code", "name", "close", "historyDays"),
    "api__global-market__futures": ("category", "items", "summary"),
    "api__global-market__options": ("category", "items", "summary"),
    "api__global-market__precious-metals": ("category", "items", "summary"),
    "api__global-market__bonds": ("category", "items", "summary"),
    "api__index": ("data", "success"),
    "api__derivatives__v1-status": ("data", "success"),
    "api__futures": ("data", "success"),
    "api__futures__TX": ("data", "success"),
    "api__futures__TX__candles": ("data", "success"),
    "api__options": ("data", "success"),
    "api__open-interest": ("data", "success"),
    "api__institution": ("data", "success"),
    "api__basis": ("data", "success"),
    "api__news": ("data", "success"),
    "api__ai-analysis": ("data", "success"),
    "api__futures__TX__technical-candles": ("data", "success"),
    "api__options__chain": ("data", "success"),
    "api__pcr": ("data", "success"),
    "api__maxpain": ("data", "success"),
    "api__us-market__etf-center": ("category", "items", "summary"),
    "api__us-market__search": ("query", "count", "results"),
    "api__us-market__listed": ("count", "results"),
    "api__us-market__nyse-listed": ("group", "results", "returned"),
    "api__us-market__options-chain__AAPL": ("symbol", "calls", "puts", "summary"),
    "api__us-market__symbol__AAPL": ("symbol", "name", "market", "source"),
    "api__us-market__sector-stocks": ("sector", "items", "usable"),
    "api__twse__all-stocks": ("snapshotDate", "count", "stocks"),
    "api__twse__etfs": ("count", "items"),
    "api__twse__stock__0050": ("code", "name", "close", "historyDays"),
    "api__twse__stock__2330__shareholders": ("code", "shareholderDistribution"),
    "api__twse__stock__2330__institutional-history": ("code", "institutionalTrades", "institutionalTradeHistory"),
}

ERROR_ONLY_ENDPOINT_NAMES = {
    "api__yahoo__sector",
    "api__yahoo__sector-chart",
}


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


def frontend_combined_source() -> str:
    """TD-02 把 app.js 拆成 app.js + js/*.js,escapeHtml() 呼叫點會隨批次分散
    到不同檔案,計數必須合併讀取,只看 app.js 會低估(跟
    security_guardrail_check.py 的同名輔助函式是同一個道理,各自獨立實作
    避免 regression/ 對外層模組產生非必要的匯入依賴)。"""
    parts = [APP_JS_PATH.read_text(encoding="utf-8")]
    js_dir = REPO_ROOT / "js"
    if js_dir.exists():
        parts.extend(p.read_text(encoding="utf-8") for p in sorted(js_dir.glob("*.js")))
    return "\n".join(parts)


def check_escapehtml_threshold() -> CheckReport:
    """工單 00 第三部分第 3 點,TD-02 期間收緊:escapeHtml 呼叫次數(合併
    app.js + js/*.js)必須精確等於基準值——純搬移工單不容許任何呼叫點
    在搬移過程中遺失,95% 門檻只適用於工單 00 當時允許的一般性重構,不適用
    於本工單這種「應該一次不少」的逐位元組搬移。"""
    report = CheckReport("escapeHtml() 呼叫次數(app.js + js/*.js)精確等於基準")
    if not ESCAPEHTML_BASELINE_PATH.exists():
        report.fail(f"找不到基準檔 {ESCAPEHTML_BASELINE_PATH}")
        return report
    baseline = json.loads(ESCAPEHTML_BASELINE_PATH.read_text(encoding="utf-8"))
    baseline_count = baseline["escapeHtml_call_count"]
    current_count = len(re.findall(r"escapeHtml\(", frontend_combined_source()))
    if current_count != baseline_count:
        report.fail(f"現況 {current_count} 次 != 基準 {baseline_count} 次(精確相等,無 95% 容忍)")
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
    with start_server(extra_env={"MARKET_PULSE_DISABLE_BACKGROUND": "1"}) as server:
        import urllib.request

        req = urllib.request.Request(server.base_url + "/api/health", headers={"User-Agent": "regression-verify"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            current_headers = {name: resp.headers.get(name) for name in baseline_headers}
    for name, expected in baseline_headers.items():
        actual = current_headers.get(name)
        if actual != expected:
            report.fail(f"{name}: 基準={expected!r} 現況={actual!r}")
    return report


def _is_external_failure(status: int, body: object) -> bool:
    """TD-17:辨識「程式碼已經正確攔截外部資料源失敗、回傳既有錯誤信封」的
    情況,跟「程式碼本身把回應格式改壞了」區分開來。fetch() 逾時/連線失敗
    回傳 status=0;app.py 的 api_exception_response() 對外部抓取失敗固定回
    502 + {"success": False, "error_code": ..., ...} 這個信封,兩者都是
    外部資料源問題,不是程式碼缺陷。"""
    if status == 0:
        return True
    if status in (502, 503, 504) and isinstance(body, dict) and body.get("success") is False and "error_code" in body:
        return True
    return False


def _format_external_failure(request_path: str, status: int, body: object) -> str:
    if status == 0 and isinstance(body, dict) and "__fetch_error__" in body:
        return f"[外部問題,非程式碼] {request_path}: 連線失敗 - {body['__fetch_error__']}"
    error_code = body.get("error_code") if isinstance(body, dict) else None
    suffix = f",error_code={error_code}" if error_code else ""
    return f"[外部問題,非程式碼] {request_path}: 狀態碼={status}{suffix}"


def _required_path_exists(body: object, path: str) -> bool:
    """只沿 object key 走 dot-path；不把 null/空值當成 key 缺失。"""
    current = body
    for segment in path.split("."):
        if not isinstance(current, dict) or segment not in current:
            return False
        current = current[segment]
    return True


def _validate_required_key_policy(endpoints: list[dict]) -> list[str]:
    """確認 manifest 與 TD-19 policy 一對一，避免 allowlist 自己形成盲區。"""
    manifest_names = [endpoint["name"] for endpoint in endpoints]
    manifest_set = set(manifest_names)
    policy_set = set(REQUIRED_KEY_PATHS)
    errors: list[str] = []

    if len(manifest_names) != len(manifest_set):
        errors.append("[verifier 設定缺漏] manifest endpoint name 不唯一")
    for name in sorted(manifest_set - policy_set):
        errors.append(f"[verifier 設定缺漏] endpoint {name} 沒有 required-key policy")
    for name in sorted(policy_set - manifest_set):
        errors.append(f"[verifier 設定缺漏] policy {name} 不存在於 manifest")

    for name, paths in REQUIRED_KEY_PATHS.items():
        if name in ERROR_ONLY_ENDPOINT_NAMES:
            if paths:
                errors.append(f"[verifier 設定缺漏] error-only endpoint {name} 不應宣告 required path")
            continue
        if not paths:
            errors.append(f"[verifier 設定缺漏] success endpoint {name} 沒有 required path")
        for path in paths:
            segments = path.split(".")
            if not path or any(not segment or any(char in segment for char in "[]*?") for segment in segments):
                errors.append(f"[verifier 設定缺漏] endpoint {name} 有非法 required path {path!r}")
    return errors


def _check_one_endpoint(server_base_url: str, endpoint: dict) -> str | None:
    """回傳 None 表示通過,否則回傳帶分類標籤(外部問題 / 程式碼問題)的失敗描述。"""
    from capture_baseline import Case

    # endpoint["request_path"] 已含 query string,整段當 url_path 即可,query 留空。
    case = Case(name=endpoint["name"], rule=endpoint["rule"], url_path=endpoint["request_path"], query={})
    status, _content_type, body = fetch(server_base_url, case)

    if _is_external_failure(status, body):
        return _format_external_failure(endpoint["request_path"], status, body)

    if status != endpoint["status_code"]:
        return f"[程式碼可能改動回應格式] {endpoint['request_path']}: 狀態碼基準={endpoint['status_code']} 現況={status}"

    if endpoint["name"] not in REQUIRED_KEY_PATHS:
        return f"[verifier 設定缺漏] {endpoint['request_path']}: 沒有 required-key policy"

    required_keys = REQUIRED_KEY_PATHS[endpoint["name"]]
    if endpoint["name"] not in ERROR_ONLY_ENDPOINT_NAMES:
        if not isinstance(body, dict):
            return f"[程式碼可能改動回應格式] {endpoint['request_path']}: 成功回應不是 object"
        missing = [path for path in required_keys if not _required_path_exists(body, path)]
        if missing:
            return f"[程式碼可能改動回應格式] {endpoint['request_path']}: 缺少必要欄位 {', '.join(missing)}"

    baseline_file = BASELINE_DIR / endpoint["baseline_file"]
    stored_value = json.loads(baseline_file.read_text(encoding="utf-8"))

    if endpoint["structure_only"]:
        current_schema = extract_schema(body)
        schema_diffs = schema_diff(stored_value, current_schema)
        if schema_diffs:
            return f"[程式碼可能改動回應格式] {endpoint['request_path']}: 回應結構(schema)與基準不同 - {'; '.join(schema_diffs[:5])}"
        return None

    masked_current = apply_mask(body, _parse_mask_paths(endpoint["mask_paths"]))
    diffs = deep_diff(stored_value, masked_current)
    if diffs:
        return f"[程式碼可能改動回應格式] {endpoint['request_path']}: {'; '.join(diffs[:5])}"
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


def _run_endpoint_checks(server_base_url: str, endpoints: list[dict]) -> dict[str, str]:
    """對一組端點逐一比對,回傳 {端點名稱: 失敗描述}(全過則為空字典)。
    第一輪失敗的端點,等待 RETRY_DELAY_SECONDS 秒後重試一次,吸收外部資料源
    偶發抖動;連續兩輪都失敗才視為真失敗。"""
    pending = {ep["name"]: ep for ep in endpoints}
    first_pass_failures: dict[str, str] = {}
    for name, endpoint in pending.items():
        failure = _check_one_endpoint(server_base_url, endpoint)
        if failure:
            first_pass_failures[name] = failure

    if first_pass_failures:
        print(f"  [verify] {len(first_pass_failures)} 個端點第一次比對失敗,{RETRY_DELAY_SECONDS} 秒後重試...")
        time.sleep(RETRY_DELAY_SECONDS)
        for name in list(first_pass_failures.keys()):
            endpoint = pending[name]
            failure = _check_one_endpoint(server_base_url, endpoint)
            if failure is None:
                del first_pass_failures[name]
            else:
                first_pass_failures[name] = failure

    return first_pass_failures


def check_api_baseline() -> CheckReport:
    """API 回應行為必須與基準一致(含遮罩時變欄位、structure-only 端點)。
    TD-17/TD-19:使用離線 fixture，避免 quick 被外部資料源影響。"""
    report = CheckReport("API 行為基準比對(快取型端點)")
    if not MANIFEST_PATH.exists():
        report.fail(f"找不到基準 manifest {MANIFEST_PATH},請先執行 capture_baseline.py")
        return report

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    policy_errors = _validate_required_key_policy(manifest["endpoints"])
    if policy_errors:
        for error in policy_errors:
            report.fail(error)
        return report
    endpoints = [ep for ep in manifest["endpoints"] if ep["name"] not in ALWAYS_LIVE_ENDPOINT_NAMES]

    with OfflineFixtureServer(MANIFEST_PATH, BASELINE_DIR) as fixture:
        failures = _run_endpoint_checks(fixture.base_url, endpoints)

    for failure in failures.values():
        report.fail(failure)
    return report


def check_api_live_baseline() -> CheckReport:
    """TD-17:比對 ALWAYS_LIVE_ENDPOINT_NAMES 這幾個設計上無快取、永遠直接
    打外部資料源的端點。獨立於 check_api_baseline(),由 --api-live/--full 呼叫,
    --quick 預設不含,避免這類端點天生的外部延遲拖累 --quick 的穩定性。"""
    report = CheckReport("API 行為基準比對(即時端點)")
    if not MANIFEST_PATH.exists():
        report.fail(f"找不到基準 manifest {MANIFEST_PATH},請先執行 capture_baseline.py")
        return report

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    policy_errors = _validate_required_key_policy(manifest["endpoints"])
    if policy_errors:
        for error in policy_errors:
            report.fail(error)
        return report
    endpoints = [ep for ep in manifest["endpoints"] if ep["name"] in ALWAYS_LIVE_ENDPOINT_NAMES]
    if not endpoints:
        report.fail("manifest 中找不到任何 ALWAYS_LIVE_ENDPOINT_NAMES 對應端點,清單可能已跟 manifest 對不上")
        return report

    with start_server() as server:
        failures = _run_endpoint_checks(server.base_url, endpoints)

    for failure in failures.values():
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


def run_interaction_compare() -> CheckReport:
    """工單 00-B 第四部分:--interactions 或 --full 執行時,前端互動行為
    (P0+P1,21 頁 94 步驟)必須全綠。P2 尚未實作,--interactions-full 目前
    等同預設,由 interaction_check.py 自己處理。"""
    report = CheckReport("interaction_check.py --compare")
    proc = subprocess.run(
        [sys.executable, str(REGRESSION_DIR / "interaction_check.py"), "--compare"],
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
    group.add_argument("--quick", action="store_true", help="快取型端點 API 比對 + 安全檢查(快、穩定,不含即時端點)")
    group.add_argument("--full", action="store_true", help="quick + --api-live + Playwright 前端比對 + 互動行為比對")
    parser.add_argument(
        "--interactions",
        action="store_true",
        help="額外執行前端互動行為比對(P0+P1);--full 已自動包含,--quick 不含",
    )
    parser.add_argument(
        "--api-live",
        action="store_true",
        help="額外比對設計上無快取、每次都直接打外部的端點(live-sectors/live-overview/"
        "live-stocks/live-search);--full 已自動包含,--quick 不含",
    )
    args = parser.parse_args()

    reports = [
        check_security_guardrail(),
        check_escapehtml_threshold(),
        check_security_headers(),
        check_api_baseline(),
    ]
    if args.full or args.api_live:
        reports.append(check_api_live_baseline())
    if args.full:
        reports.append(run_frontend_compare())
        reports.append(run_interaction_compare())
    elif args.interactions:
        reports.append(run_interaction_compare())

    for report in reports:
        report.print_result()

    ok = all(report.ok for report in reports)
    print(f"\n{'VERIFY_OK' if ok else 'VERIFY_FAILED'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
