# TD-13 REMAIN-01～03 執行證據

日期：2026-09-01

## Inventory

`python regression/td13_exception_inventory.py` 對 production Python modules 進行 AST 盤點：

| 分類 | 數量 | 決策 |
|---|---:|---|
| direct-log | 131 | 已有最低限度 logger／exception logging |
| delegated-api-error-log | 25 | 由 `api_exception_response()` 統一記錄，對外仍回安全錯誤 envelope |
| translate-or-reraise | 5 | backend health／fault 邊界需轉譯或 re-raise，不靜默吞錯 |
| fallback-without-direct-log | 0 | 無未決靜默 broad exception |
| 合計 | 161 | 全數有分類與決策 |

本批 logging 僅保留 stock code、market、date、component、fallback 等診斷 context；API exception log 不記錄 query value，測試會以 `secret-query-value` fault injection 驗證。

## 驗證

```text
python -m unittest test_derivatives_platform.py regression.test_offline_verifier
Ran 185 tests ... OK
python security_guardrail_check.py
SECURITY_GUARDRAIL_OK: 16 passed
python regression/verify_against_baseline.py --full
VERIFY_OK
```

原有 response、fallback、錯誤狀態與 rate-limit／cache 邊界均未改寫；`.gitattributes` 的 LF 政策維持不變。

回退單位：逐 hunk 還原 logging／inventory／fault-injection test，不撤銷 `.gitattributes`。
