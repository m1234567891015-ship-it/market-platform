# TD02-03 `runtime/api` shadow-only proof（2026-08-31）

## 1. 批次界線

本批依 TD02-02 選定最低風險的 `js/api.js` 作為 `runtime/api` candidate，僅在系統 temp 目錄建立一次性 ESM wrapper 與 Node harness。**沒有建立正式 ESM module、沒有修改 HTML／classic source／bundle／source map／baseline／CSP／headers／Service Worker／cache／deployment／SQLite／`twse-cache.json`。**

可重跑 verifier：

```text
python regression/td02_03_api_shadow.py --check
```

通過輸出前綴：`TD02_03_SHADOW_OK`。

## 2. 候選與靜態證據

| gate | 結果 | 證據 |
|---|---|---|
| module candidate | ✅ | `runtime/api` ← `js/api.js` |
| symbol ownership | ✅ | 唯一頂層 symbol：`fetchWithTimeout`；matrix owner 為 `js/api.js` |
| classic order | ✅ | `js/core.js → js/api.js → js/shared-calc.js`，符合 TD-18 lockfile |
| dependency／cycle | ✅ | TD02-01 matrix 中 `js/api.js` 無 incoming/outgoing dependency edge |
| top-level initialization | ✅ | `js_top_level_immediate_statement_identifiers` 為空；無 baseline global 引用 |
| DOM／window isolation | ✅ | `document`、`window`、`localStorage`、`location`、`innerHTML` 均未出現在 slice |
| `escapeHtml` single source | ✅ | 全站 `app.js + js/*.js` 僅 1 份 definition，owner 為 `js/core.js` |

本次 source fingerprint：

```text
js/api.js SHA-256 = 9a633652fedd9d98d939a97a0ef42fb133a482f899a622c1a3f652a7c9eb20be
```

## 3. Runtime shadow evidence

隔離 wrapper 在 Node ESM loader 中加入 `export { fetchWithTimeout }`，未改動 production source。harness 驗證：

| case | 結果 |
|---|---|
| named export | ✅ 僅 `fetchWithTimeout` |
| import initialization | ✅ import 時 fetch call = 0 |
| success | ✅ status 200；保留 `GET` options；附帶 AbortController signal |
| upstream rejection | ✅ 保留注入的 `injected upstream failure` |
| timeout／abort | ✅ 收到 `AbortError`，且 timeout cleanup 路徑完成 |

## 4. Rollback 與 gate 結論

本批 rollback 只需移除 `regression/td02_03_api_shadow.py` 與本 proof report；現行 classic source、TD-18 lockfile 與 production wiring 不受影響，無需回復 HTML 或 bundle。

TD02-03 shadow-only proof：✅ 完成。這個結果只授權後續提出正式接線方案；**不授權本批或自動推定可修改正式 HTML／ESM wiring**。
