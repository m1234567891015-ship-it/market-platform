# TD-19 REMAIN-01～03 closure

日期：2026-09-01

## 契約對帳

- baseline manifest：44 endpoints。
- `REQUIRED_KEY_PATHS` policy：44 entries，manifest／policy 一對一，無漏列或多餘列。
- required path 只驗證 key presence；`null`、空陣列、空字串與合法零值不因 TD-19 直接失敗。
- Yahoo sector／sector-chart 維持明示 `error-only`，不把錯誤 fixture 冒充 healthy success。
- structure-only response 的非關鍵時變 key 仍由既有 `schema_diff()` 規則處理。

## Fault injection 與驗證

`regression/test_offline_verifier.py` 的 8 個案例覆蓋：

- 移除頂層／巢狀 required key → 以 `[程式碼可能改動回應格式]` FAIL。
- required key 值為 `null`／空集合 → pass presence check。
- 外部 502 error envelope → 先分類為 `[外部問題,非程式碼]`。
- success response 非 object、未知 policy、非法 policy entry → 以可讀 failure label FAIL。

```text
python -m unittest regression.test_offline_verifier
Ran 8 tests ... OK
python regression/verify_against_baseline.py --quick
VERIFY_OK
python regression/verify_against_baseline.py --full
VERIFY_OK
```

未更新 baseline；回退單位為 policy／fixture／test diff，保留既有 structure-only 容忍範圍。
