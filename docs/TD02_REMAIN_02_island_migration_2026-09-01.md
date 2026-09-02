# TD02-REMAIN-02 單一頁面 ESM island migration

日期：2026-09-01  
狀態：✅ 本批 migration／回退 proof 通過；完整驗證的外部項目另列如下

## 範圍與選擇

本批選定 `derivatives-status.html` 的 page-specific addon 作為單一 island。其他 20
頁維持原本的 `common-runtime.min.js → route-bundle.min.js` wiring；既有
`derivatives-status-addon.min.js` 保留為 classic fallback。

正式頁面現在載入外部 `derivatives-status-esm-loader.js`。loader 在支援 ESM 的瀏覽器
啟動 `derivatives-status-esm.js`；legacy browser 或 module load error 則只載入既有
`derivatives-status-addon.min.js`，並以 guard 確保 fallback 不重複載入。

## 變更檔案

- `derivatives-status-esm.js`：ESM island，export `startDerivativesStatus`。
- `derivatives-status-esm-loader.js`：classic loader／fallback。
- `derivatives-status.html`：只替換 status addon 的入口。
- `market_config.py`：加入兩個 ESM asset 的 root static whitelist。
- `regression/td18_shadow_verify.py`：讓既有 TD18 wiring verifier 識別 status ESM loader；其他 bundle 順序規則不變。
- `regression/td02_remain_02_island_migration.py`：本批 static／runtime／fallback verifier。

## Proof 結果

| gate | 結果 | 證據 |
|---|---|---|
| 895／895 inventory | ✅ | matrix、global-symbol baseline 與 unique owner 均為 895 |
| ESM runtime | ✅ | named export、一次 DOMContentLoaded、一次 API fetch、DOM render 與 escapeHtml 通過 |
| classic fallback | ✅ | noModule 舊瀏覽器與 module load error 均回退既有 addon，且只載入一次 |
| status page wiring | ✅ | 21 頁清單完整，只有 `derivatives-status.html` 使用 ESM loader |
| security／CSP | ✅ | security guardrail 16/16；TD18 shadow verifier H10_02_VERIFY_OK、CSP 與 local asset 404=0 |
| interaction | ✅ | 94/94 PASS；`derivatives-status.html` 互動路徑通過 |
| pixel／API full verify | ⚠️ 外部問題 | status page 未出現未分類差異；其餘頁面受 `ERR_NETWORK_ACCESS_DENIED`，live API 受 TAIFEX／Yahoo 502 影響，未更新 baseline |

## 其他驗證

- `python -m unittest test_derivatives_platform.py`：176 tests PASS。
- `node --check derivatives-status-esm.js`、loader 與既有 minified fallback：通過。
- `python e2e_smoke.py`：`E2E_SMOKE_OK`。
- `python regression/td02_remain_02_island_migration.py`：`TD02_REMAIN_02_ISLAND_OK`。
- `python regression/td18_shadow_verify.py`：`H10_02_VERIFY_OK`。

## 回退

恢復 `derivatives-status.html` 的原始 `derivatives-status-addon.min.js` script，移除兩個
ESM asset 及 `ROOT_STATIC_FILES` whitelist entries；不需修改其他頁面、baseline、CSP、
Service Worker、部署設定或資料。

本批未 commit。工作樹中其他既有 modified／untracked 檔案及 baseline 變更未由本批處理。
