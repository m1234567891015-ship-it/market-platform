# TD02-REMAIN 驗證閉環

日期：2026-09-01  
結論：✅ TD02-REMAIN-01～03 驗證閉環完成；完整 baseline 已在允許外網環境通過

## 閉環修正

REMAIN-01 原 verifier 只接受 REMAIN-02 之前的
`derivatives-status-addon.min.js` wiring，因此在 REMAIN-02 已核准切換到單頁
`derivatives-status-esm-loader.js` 後會產生過時的 false negative。本次只更新
verifier 契約，使其同時驗證：

- 既有 classic status addon wiring；或
- REMAIN-02 核准的 ESM loader wiring，並確認 ESM、loader、classic fallback 資產均存在。

未回退 production wiring、未擴大頁面範圍、未修改 baseline。

## 批次結果

| 批次 | 現況驗證 | 主要結果 |
|---|---|---|
| TD02-REMAIN-01 | ✅ `TD02_REMAIN_01_SHADOW_OK` | 895/895 inventory、bridge、API timeout/error、classic fallback、CSP／escapeHtml；current status wiring 正確識別為 ESM loader |
| TD02-REMAIN-02 | ✅ `TD02_REMAIN_02_ISLAND_OK` | 21 頁 wiring、單頁 ESM island、DOM／error escape、classic fallback 與 rollback 通過 |
| TD02-REMAIN-03 | ✅ `TD02_REMAIN_03_CANARY_OK` | ESM／強制 rollback 各 1 次 status API、正常渲染、無 page／console error、無 polling |

## 專案護欄

- `python -m unittest test_derivatives_platform.py`：176 tests PASS。
- `python security_guardrail_check.py`：16/16 PASS。
- `python e2e_smoke.py`：`E2E_SMOKE_OK`。
- `python regression/td18_shadow_verify.py`：`H10_02_VERIFY_OK`，21 頁、895/895、local asset 404=0。
- `python regression/interaction_check.py --compare`：94/94 PASS。
- Node／Python syntax checks：通過。

## Full baseline 最終結果

先前受限網路環境會造成 Google Fonts 封鎖與 live API 502。經核准在可存取外部
資料源的環境重跑後：

- `python regression/verify_against_baseline.py --full`：`VERIFY_OK`。
- live API、frontend compare、interaction compare 全部 PASS。
- `derivatives-status.html` 正常通過，未更新 baseline。

先前受限環境的錯誤未藉由更新 baseline 掩蓋；baseline 保持不變。

本次未 commit；其他既有 modified／untracked 檔案不在本閉環範圍內。
