# TD02-REMAIN-03 單頁 ESM canary 與回退驗證

日期：2026-09-01  
狀態：✅ canary 通過；完整驗證的外部項目另列如下

## 範圍

本批只觀測 `derivatives-status.html`，未擴大 production page scope，也未修改
baseline。canary 使用既有 status-page HAR，分別執行正常 ESM 模式與明確指定
`?td02-esm=off` 的 classic rollback 模式。

## Canary 結果

| 項目 | 正常 ESM | 強制 rollback |
|---|---|---|
| loader state | `esm-active` | `classic-fallback` |
| page-specific asset | `derivatives-status-esm.js` | `derivatives-status-addon.min.js` |
| status API fetch | 1 次 | 1 次 |
| 另一條 asset path | 未載入 classic fallback | 未載入 ESM module |
| DOMContentLoaded listener | ESM 0（允許上限 1） | fallback 0（允許上限 1） |
| ESM interval | 0 | 0 |
| page／console error | 0 | 0 |
| status island render | ✅ | ✅ |

回退 loader 另處理 dynamic classic script 晚於 `DOMContentLoaded` 載入的時序：只
對 fallback 自己註冊的初始化回呼提供一次性補呼叫，並在 script load/error 後還原
`document.addEventListener`；不重新派送全域事件，也不影響其他頁面。

## 護欄與完整驗證

- `python regression/td02_remain_03_canary.py`：`TD02_REMAIN_03_CANARY_OK`。
- `python regression/td02_remain_02_island_migration.py`：`TD02_REMAIN_02_ISLAND_OK`。
- `python security_guardrail_check.py`：16/16 PASS。
- `python -m unittest test_derivatives_platform.py`：176 tests PASS。
- `python e2e_smoke.py`：`E2E_SMOKE_OK`。
- `python regression/td18_shadow_verify.py`：`H10_02_VERIFY_OK`，21 頁、895/895、
  local asset 404=0。
- `python regression/interaction_check.py --compare`：94/94 PASS。
- `python regression/verify_against_baseline.py --full`：在允許外網的驗證環境重跑，
  `VERIFY_OK`；live API、frontend compare、interaction compare 全部 PASS，未更新
  baseline。

## 回退順序

設定 `?td02-esm=off` 或停用 ESM loader → 載入既有
`derivatives-status-addon.min.js` → 若移除 island，再恢復原 status script wiring。

本批未 commit；工作樹中其他既有 modified／untracked 檔案及 baseline 變更未由本批
處理。
