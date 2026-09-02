# TD-19 Required-key Allowlist 設計

本文件為 H-07-02 產出，將 [TD19 required-key 欄位政策盤點](TD19_required_key_matrix_2026-08-31.md) 轉成可實作、可測試的 verifier 契約。本批只確認設計與測試案例，不把規則擴充或 baseline 更新混入實作批次。

## 1. Allowlist schema

allowlist 以 manifest 的 `name` 作為唯一 key，每個 endpoint 都必須有一筆政策；政策不是只有 required 欄位清單，還要能表達「暫不要求但有理由」的 endpoint，避免漏登記被靜默放過。

概念 schema：

```text
RequiredKeyPolicy = {
  endpoint_name: {
    mode: "success" | "error-only" | "not-required",
    required_paths: ["topLevelKey", "nested.object.key"],
    rationale: "why this endpoint is or is not guarded",
  }
}
```

規則：

- `mode=success` 時，`required_paths` 至少一項；預期成功 status 且 response 是 object 才做存在性檢查。
- `mode=error-only` 用於目前只有錯誤 fixture 的 endpoint；本階段不把錯誤 envelope 的 `error` 直接當成成功契約，待 healthy fixture 補齊後再轉成 `success`。
- `mode=not-required` 只允許在 matrix 有明確理由時使用，並由 coverage test 確認不是漏列。
- path 只支援 object key 與 dot-path；第一版禁止 array index、wildcard、regex 與「任一 key 存在」語意。
- required 的語意是 key presence：key 存在但 value 為 `null`、空陣列、空字串或合法的零值，不因 TD-19 直接失敗；非空、型別、數值範圍由既有 schema／domain contract 處理。
- 同一 response 可同時受 required-key check 與既有 `schema_diff()`／value diff 保護；required-key check 不取代既有比對。

## 2. Failure classification

檢查順序固定如下，避免把外部故障誤報成程式碼格式回歸：

1. 若 response 符合既有外部失敗判定，回報 `[外部問題,非程式碼]`，不執行 required-key check。
2. 若 HTTP status 不等於 manifest 預期 status，沿用既有 `[程式碼可能改動回應格式]` 狀態碼錯誤。
3. 若政策為 `success` 但 body 不是 object，回報 `[程式碼可能改動回應格式]`，指出 response body 型態不符。
4. 逐一檢查 required path；父 object 或 leaf key 缺少時，回報 endpoint、path 與 missing key。
5. required keys 都存在後，繼續既有 structure-only／value compare；新增或時變欄位仍依既有規則處理。

錯誤訊息至少要包含：manifest endpoint name 或 request path、完整 required path、分類標籤。不得把 response body 原文寫入錯誤訊息，避免洩漏外部資料或 secrets。

## 3. Coverage policy

- 44/44 manifest endpoints 必須有 policy entry；`required_paths=[]` 只能搭配 `error-only` 或 `not-required`，且必須有 rationale。
- coverage test 要同時檢查：manifest 多出 endpoint 時 fail、allowlist 多出不存在 endpoint 時 fail、`success` 空 required list 時 fail、非法 array-index／wildcard path 時 fail。
- 2330／0050 使用同一 response contract 時，仍需讓兩筆 manifest endpoint 各自有 policy entry，避免只因一個代表 symbol 通過而漏保護另一個。
- Yahoo sector／sector-chart 在 healthy fixture 尚未存在前維持 `error-only`；不能以目前的 error-only baseline 宣稱成功 response 已受 required-key 保護。

## 4. Test case matrix

| ID | 情境 | 預期結果 | 分類 |
|---|---|---|---|
| K-01 | 成功 object 缺少頂層 required key | fail，列出 endpoint 與 missing key | 程式碼可能改動回應格式 |
| K-02 | 成功 object 缺少 dot-path 的 parent 或 leaf | fail，列出完整 path | 程式碼可能改動回應格式 |
| K-03 | required key 存在但 value 是 `null` | pass required-key check | 合法空資料 |
| K-04 | required key 存在但 value 是空陣列／零值 | pass required-key check | 合法空資料 |
| K-05 | response 多出未列入的 key | 不由 TD-19 報錯，交給既有 schema 規則 | 既有 structure-only 語意 |
| K-06 | 預期成功但 body 是 list／string／null | fail，指出 body 型態不符 | 程式碼可能改動回應格式 |
| K-07 | upstream 502／timeout／既有 external failure body | 不執行 required-key check | 外部問題，非程式碼 |
| K-08 | status code 與 manifest 預期不同 | 沿用既有 status failure | 程式碼可能改動回應格式 |
| K-09 | manifest endpoint 沒有 policy entry | coverage test fail | verifier 設定缺漏 |
| K-10 | policy 有不存在的 endpoint 或非法 path syntax | coverage/config test fail | verifier 設定缺漏 |
| K-11 | 2330 缺 key、0050 完整（或反向） | 對應 endpoint 單獨 fail | symbol-specific contract |
| K-12 | error-only policy 收到錯誤 fixture | 只驗證 error classification，不宣告 healthy required keys | 待補成功 fixture |

## 5. 實作與回退邊界

H-07-03 才把此 schema 接入 offline fixture／`--quick` verifier，並以 K-01～K-12 的 mutation tests 證明護欄會在故意移除欄位時紅燈。H-07-04 才把同一政策帶入 `--api-live`／`--full`。

回退單位是單一 regression verifier commit 與其專用測試；不得回退產品 API，不得刪除或改寫既有 baseline 來消除 required-key failure。若 healthy fixture、endpoint owner 或空資料語意未能確認，保留 `error-only`／`not-required` 並記錄理由，不猜測 required key。

## H-07-02 驗證結果

- 設計測試案例數：`12`
- `python -m py_compile app.py regression/verify_against_baseline.py`：PASS
- `python -m unittest test_derivatives_platform.py regression/test_offline_verifier.py`：177 tests PASS
- `python regression/verify_against_baseline.py --quick`：`VERIFY_OK`
- `python security_guardrail_check.py`：16/16 PASS
- `python e2e_smoke.py`：`E2E_SMOKE_OK`
- `python regression/verify_against_baseline.py --full`：允許外部連線重跑為 `VERIFY_OK`，21 頁 frontend、94 條 interaction、cached/live API 與 security 全部 PASS
- 本批只新增設計文件；未擴充 verifier，未更新 golden baseline，未修改產品 API、CSP 或部署設定。

## H-07-03 實作與驗證結果

- `regression/verify_against_baseline.py` 已接入 44/44 manifest policy coverage、object dot-path、body type 與 required-key presence 檢查；external failure 仍在 required-key 前先分類。
- `regression/test_offline_verifier.py` 已覆蓋缺少頂層／巢狀 key、合法 `null`／空資料、external failure 優先、非 object body 與 unknown policy coverage；183 tests 全部 PASS。
- `python regression/verify_against_baseline.py --quick`：`VERIFY_OK`；`python security_guardrail_check.py`：16/16 PASS；`python e2e_smoke.py`：`E2E_SMOKE_OK`；外部連線 `python regression/verify_against_baseline.py --full`：`VERIFY_OK`。
- 本批只修改 regression verifier、TD-19 regression tests 與文件；未修改產品 API、CSP、部署設定或 golden baseline。H-07-04 仍需進行 live/full rollout 最終核對與封存。

## H-07-04 Live／full rollout 驗證結果

- 44/44 manifest policy coverage 通過；required-key check 已由 offline／quick 延伸至 live／full，external failure 仍先分類。
- `python -m py_compile app.py regression/verify_against_baseline.py regression/test_offline_verifier.py`：PASS
- `python -m unittest test_derivatives_platform.py regression/test_offline_verifier.py`：183 tests PASS
- `python regression/verify_against_baseline.py --quick`：`VERIFY_OK`
- `python security_guardrail_check.py`：16/16 PASS
- `python e2e_smoke.py`：`E2E_SMOKE_OK`
- `python regression/verify_against_baseline.py --full`：允許外部連線重跑為 `VERIFY_OK`，cached/live API、21 頁 frontend、94 條 interaction 與 security 全部 PASS
- H-07 驗收完成；未更新 golden baseline，未修改產品 API、CSP 或部署設定。回退保留 classic／既有 verifier 行為，採單一 regression verifier commit 回退。
