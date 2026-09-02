# TD-02 全站 ESM Phase 3～4 closure（2026-09-01）

## 結論

TD-02 全站 ESM Phase 3～4 已完成正式前端接線與驗證。21 頁現在由
`market-pulse-esm-loader.js` 進入 full-site ESM；loader 保留 module load error、
legacy browser 與 `td02-esm=off` 的 classic fallback。classic source／minified bundle、
source map 與 rollback path 均保留，未刪除 legacy safety net。

## 實作內容

- 以既有 source order 建立 deterministic `market-pulse-esm.min.js`，納入 895-symbol
  transitional bridge，source map 可追溯至各 locked input。
- 21 個 HTML entry 統一接到 `market-pulse-esm-loader.js`。
- fallback 順序固定為 `common-runtime.min.js` → `route-bundle.min.js`；
  `derivatives-status.html` 額外載入 `derivatives-status-addon.min.js`。
- rollback query 以 session-scoped marker 跨頁保存；`derivatives-ai.html` 轉址後仍維持
  classic mode。
- 新增 full-ESM root asset whitelist、immutable cache version 與 Service Worker cache version。
- `derivatives-status-esm.js` 改為同時支援 full bundle lexical `escapeHtml` 與 standalone global bridge，
  未複製 `escapeHtml` implementation。

## 驗證證據

| Gate | 結果 |
|---|---|
| full ESM build | `TD02_FULL_ESM_BUILD`；bundle 1,508,130 bytes，source map 2,754,104 bytes；895 bridge symbols |
| normal／rollback browser canary | 21 頁 × 2 modes = 42/42 通過；DOM counts 與 baseline 一致；無 page／console error |
| rollback coverage | 包含 `derivatives-ai.html` 轉址與 `derivatives-status.html` addon fallback |
| frontend screenshot baseline | `frontend_check.py --compare` PASS；未更新 baseline |
| interaction baseline | 94/94 steps PASS |
| H-10 shadow verifier | 21/21 pages、CSP、local asset 404=0、immutable cache、895 classic fallback symbols PASS |
| security guardrail | 16/16 PASS |
| unit／offline contract | 185 tests PASS |
| E2E | `E2E_SMOKE_OK` |
| full regression | `VERIFY_OK` |

## 產物與回退

- Build manifest：`docs/TD02_FULL_ESM_build_manifest_2026-09-01.json`
- ESM entry：`market-pulse-esm.min.js`
- Loader：`market-pulse-esm-loader.js`
- 回退方式：載入頁面時使用 `?td02-esm=off`，或由 loader 在 module load error 時自動回到
  classic bundles；不修改 SQLite、`twse-cache.json` 或 TD-03 worker／Redis 設定。

