# TD-10 REMAIN-01～03 執行證據

日期：2026-09-01

## 結果

- top-10 清單固定於 `tests/fixtures/td10_large_function_contracts.json`，10/10 函式均有 owner 輸入 fixture、required output 與測試名稱對應。
- 測試使用離線資料與 mock，不依賴即時 TWSE／TAIFEX／Yahoo。
- 正常契約、空資料／格式邊界，以及適用的上游失敗／fallback 分支均有測試；不適用的分支保留為 `null` 並由 matrix 明示。
- `test_td10_top10_contract_matrix_is_complete` 會故意檢查清單數量、函式可呼叫性、測試對應與 required output，避免只增加測試數量而漏項。

## 驗證

```text
python -m unittest test_derivatives_platform.py regression.test_offline_verifier
Ran 185 tests ... OK
python regression/verify_against_baseline.py --quick
VERIFY_OK
python regression/verify_against_baseline.py --full
VERIFY_OK
```

完整回歸的 21 頁 frontend、94/94 interaction、security 與 API quick/live 均通過；未更新 baseline。

回退單位：移除本批 fixture／tests／matrix，不需回退 production source。
