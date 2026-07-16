"""工單 00 第一部分:抓取 API 行為基準。

只在「原版」(重構前)執行一次。用法:

    python regression/capture_baseline.py

會啟動一份獨立的 app.py(臨時 DB/cache 路徑,不動到專案根目錄的執行期資料),
對全部 API GET 端點各抓取固定測試參數的回應,抓兩次(間隔 10 秒)以抓出
時變欄位並建立遮罩規則,最後把結果寫入 baseline/api/*.json 與 manifest.json。
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parent))

from diffing import apply_mask, detect_dynamic_paths, extract_schema, mask_paths_to_str  # noqa: E402
from route_scan import Route, api_get_routes  # noqa: E402
from server_harness import start_server  # noqa: E402

REGRESSION_DIR = Path(__file__).resolve().parent
BASELINE_DIR = REGRESSION_DIR / "baseline"
API_BASELINE_DIR = BASELINE_DIR / "api"
MANIFEST_PATH = BASELINE_DIR / "manifest.json"
SECURITY_HEADERS_PATH = BASELINE_DIR / "security_headers.json"
ESCAPEHTML_BASELINE_PATH = BASELINE_DIR / "escapehtml_baseline.json"
APP_JS_PATH = REGRESSION_DIR.parent / "app.js"

# 工單 00 第三部分第 4 點:必須與基準完全一致的安全標頭。
SECURITY_HEADER_NAMES = [
    "Content-Security-Policy",
    "X-Frame-Options",
    "Strict-Transport-Security",
    "X-Content-Type-Options",
    "Referrer-Policy",
    "Permissions-Policy",
]

# 固定測試參數(見工單 00 第一部分第 4 點):台股 2330、0050;美股 AAPL。
TW_STOCK_CODES = ["2330", "0050"]
US_SYMBOL = "AAPL"
TW_FUTURES_SYMBOL = "TX"
TW_OPTION_UNDERLYING = "TXO"
GLOBAL_MARKET_CATEGORIES = ["us-stocks", "futures", "options", "precious-metals", "bonds"]

# 絕大多數端點的內容源自即時報價(TWSE/TAIFEX/Yahoo),數值會持續變動,
# 不是「抓兩次間隔 10 秒」就能抓完所有時變欄位(報價可能幾分鐘才更新一次,
# 但幾分鐘後再跑 verify 時就會整批不一致)。這與工單第一部分第 5 點
# 「外部資料源不穩定時,以結構(schema)比對取代全值比對」是同一件事:
# 只有這裡列出、內容確定是靜態設定/版本資訊(不含即時報價)的端點才做
# 全值 + 遮罩比對,其餘一律 structure-only。
STATIC_VALUE_ENDPOINT_NAMES = {"api__health", "api__derivatives__v1-status"}

# 依路徑前綴設定 query string 覆寫,對應 app.py 內各端點實際讀取的參數名稱。
QUERY_OVERRIDES: dict[str, dict[str, str]] = {
    "/api/futures": {"sort": "open_interest"},
    "/api/futures/{symbol}/candles": {"interval": "day"},
    "/api/futures/{symbol}/technical-candles": {"interval": "day"},
    "/api/options": {"underlying": TW_OPTION_UNDERLYING},
    "/api/options/chain": {"underlying": TW_OPTION_UNDERLYING},
    "/api/pcr": {"underlying": TW_OPTION_UNDERLYING},
    "/api/maxpain": {"underlying": TW_OPTION_UNDERLYING},
    "/api/ai-analysis": {"target": TW_OPTION_UNDERLYING},
    "/api/open-interest": {"symbol": TW_FUTURES_SYMBOL},
    "/api/twse/search": {"q": "2330"},
    "/api/us-market/search": {"q": US_SYMBOL},
}

# 需要多組固定測試參數的路徑樣板(其餘含路徑參數的端點只跑一組)。
MULTI_CASE_PATH_PARAMS: dict[str, list[dict[str, str]]] = {
    "/api/twse/stock/<code>": [{"code": c} for c in TW_STOCK_CODES],
    "/api/global-market/<category>": [{"category": c} for c in GLOBAL_MARKET_CATEGORIES],
}

DEFAULT_PATH_PARAM_VALUES = {
    "code": TW_STOCK_CODES[0],
    "category": GLOBAL_MARKET_CATEGORIES[0],
}


def _default_symbol_value(route_path: str) -> str:
    return US_SYMBOL if route_path.startswith("/api/us-market/") else TW_FUTURES_SYMBOL


@dataclass
class Case:
    name: str
    rule: str
    url_path: str
    query: dict[str, str]

    @property
    def request_path(self) -> str:
        if self.query:
            return f"{self.url_path}?{urlencode(self.query)}"
        return self.url_path


def _query_for(rule: str) -> dict[str, str]:
    template_key = re.sub(r"<[^:>]*:?([a-zA-Z_]+)>", r"{\1}", rule)
    return dict(QUERY_OVERRIDES.get(template_key, {}))


def _safe_name(case_url: str) -> str:
    name = case_url.strip("/").replace("/", "__")
    name = re.sub(r"[^a-zA-Z0-9_.=&?-]", "_", name)
    return name or "root"


def build_cases(routes: list[Route]) -> list[Case]:
    cases: list[Case] = []
    for route in routes:
        if route.path in MULTI_CASE_PATH_PARAMS:
            for params in MULTI_CASE_PATH_PARAMS[route.path]:
                url_path = route.path
                for key, value in params.items():
                    url_path = url_path.replace(f"<{key}>", value)
                query = _query_for(route.path)
                cases.append(Case(name=_safe_name(url_path), rule=route.path, url_path=url_path, query=query))
            continue

        params = re.findall(r"<(?:[a-zA-Z_]+:)?([a-zA-Z_]+)>", route.path)
        if "filename" in params:
            continue  # 靜態檔案 catch-all,不屬於 API 行為基準範圍
        url_path = route.path
        for param in params:
            value = DEFAULT_PATH_PARAM_VALUES.get(param) or _default_symbol_value(route.path)
            url_path = re.sub(rf"<(?:[a-zA-Z_]+:)?{param}>", value, url_path)
        query = _query_for(route.path)
        cases.append(Case(name=_safe_name(url_path), rule=route.path, url_path=url_path, query=query))
    return cases


_DEGENERATE_ONLY_KEYS = {"error", "error_code", "success", "__fetch_error__", "__non_json_body_len__", "__content_type__"}


def _looks_degenerate(body: object) -> bool:
    """判斷回應是不是「只有錯誤/逾時外殼,沒有真正的資料欄位」。"""
    if not isinstance(body, dict) or not body:
        return not isinstance(body, dict)
    return set(body.keys()) <= _DEGENERATE_ONLY_KEYS


def fetch(base_url: str, case: Case) -> tuple[int, str, object | None]:
    url = base_url + case.request_path
    req = urllib.request.Request(url, headers={"User-Agent": "regression-capture"})
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            status = resp.status
            content_type = resp.headers.get("Content-Type", "")
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        status = exc.code
        content_type = exc.headers.get("Content-Type", "") if exc.headers else ""
        raw = exc.read()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return 0, "", {"__fetch_error__": str(exc)}

    body: object | None
    if "application/json" in content_type:
        try:
            body = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            body = {"__non_json_body_len__": len(raw)}
    else:
        body = {"__non_json_body_len__": len(raw), "__content_type__": content_type}
    return status, content_type, body


def capture_escapehtml_baseline() -> dict:
    """記錄 app.js 目前的 escapeHtml(...) 呼叫次數,做為 95% 下限的基準值。

    實測結果為 2,037 次,與 CLAUDE.md 記載的基準值一致。仍然選擇實際掃描
    而非寫死常數,是為了讓基準永遠反映抓取當下的真實狀態(工單「自我一致性」
    要求:未改任何程式碼時 verify --full 必須 100% 通過)。
    """
    source = APP_JS_PATH.read_text(encoding="utf-8")
    count = len(re.findall(r"escapeHtml\(", source))
    data = {"escapeHtml_call_count": count, "threshold_pct": 95}
    ESCAPEHTML_BASELINE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(f"[capture] 已寫入 {ESCAPEHTML_BASELINE_PATH} (escapeHtml 呼叫次數={count})")
    return data


def capture_security_headers(base_url: str) -> dict:
    req = urllib.request.Request(base_url + "/api/health", headers={"User-Agent": "regression-capture"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        headers = {name: resp.headers.get(name) for name in SECURITY_HEADER_NAMES}
    SECURITY_HEADERS_PATH.write_text(json.dumps(headers, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(f"[capture] 已寫入 {SECURITY_HEADERS_PATH}")
    return headers


def capture() -> dict:
    routes = api_get_routes()
    cases = build_cases(routes)
    API_BASELINE_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[capture] {len(routes)} 個 API GET 路由, {len(cases)} 組測試案例")
    with start_server() as server:
        print(f"[capture] 伺服器就緒: {server.base_url}")

        round1: dict[str, tuple[int, str, object]] = {}
        for case in cases:
            print(f"  [round1] {case.request_path} ...", flush=True)
            round1[case.name] = fetch(server.base_url, case)
        print("[capture] 第一輪抓取完成,等待 10 秒偵測時變欄位...")
        time.sleep(10)

        round2: dict[str, tuple[int, str, object]] = {}
        for case in cases:
            print(f"  [round2] {case.request_path} ...", flush=True)
            round2[case.name] = fetch(server.base_url, case)
        print("[capture] 第二輪抓取完成")

        capture_security_headers(server.base_url)

        # structure-only 端點常依賴較慢的外部資料源(法人籌碼、活動日期等),
        # round2 當下若剛好抓到逾時/錯誤回應,基準就會被鎖定成「殘缺版本」,
        # 之後每次 verify 只要抓到正常的豐富回應反而會被判定為「多了欄位」。
        # 這裡在收尾前針對明顯degenerate的回應多重試幾次,盡量把基準寫成
        # 正常情況下的完整結構。
        for case in cases:
            status2, _, body2 = round2[case.name]
            structure_only = case.name not in STATIC_VALUE_ENDPOINT_NAMES or status2 != 200
            if structure_only and _looks_degenerate(body2):
                for _ in range(3):
                    retry_status, retry_ct, retry_body = fetch(server.base_url, case)
                    if not _looks_degenerate(retry_body):
                        round2[case.name] = (retry_status, retry_ct, retry_body)
                        print(f"  [retry-healthy] {case.request_path} 改用重試後的完整回應")
                        break
                    time.sleep(2)

    capture_escapehtml_baseline()

    manifest_endpoints = []
    for case in cases:
        status1, _, body1 = round1[case.name]
        status2, content_type2, body2 = round2[case.name]

        structure_only = case.name not in STATIC_VALUE_ENDPOINT_NAMES or status2 != 200 or status1 != status2
        mask_paths: list = []
        if not structure_only and isinstance(body1, dict) and isinstance(body2, dict):
            mask_paths = detect_dynamic_paths(body1, body2)

        if structure_only:
            stored_value = extract_schema(body2)
        else:
            stored_value = apply_mask(body2, mask_paths)

        out_path = API_BASELINE_DIR / f"{case.name}.json"
        out_path.write_text(json.dumps(stored_value, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

        manifest_endpoints.append(
            {
                "name": case.name,
                "rule": case.rule,
                "request_path": case.request_path,
                "status_code": status2,
                "content_type": content_type2,
                "structure_only": structure_only,
                "mask_paths": mask_paths_to_str(mask_paths),
                "baseline_file": f"api/{case.name}.json",
            }
        )
        flag = "structure-only" if structure_only else f"mask={len(mask_paths)}"
        print(f"  [{status2:>3}] {case.request_path}  ({flag})")

    manifest = {
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "route_count": len(routes),
        "endpoint_count": len(manifest_endpoints),
        "endpoints": manifest_endpoints,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(f"[capture] 已寫入 {MANIFEST_PATH} 與 {len(manifest_endpoints)} 個 baseline/api/*.json 檔案")
    return manifest


if __name__ == "__main__":
    capture()
