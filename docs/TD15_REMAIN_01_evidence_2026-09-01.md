# TD15-REMAIN-01 CSS manifest rebaseline evidence

日期：2026-09-01  
狀態：✅ `TD15-REMAIN-01` 通過；本批零刪除

## 交付結果

- 以目前工作樹重建 R0 inventory：`TD15_R0_OK`。
- 新增 [逐 rule-block 三層 evidence manifest](TD15_REMAIN_01_css_rebaseline_2026-09-01.json)。
- 263 個含候選 class 的 rule blocks，0 個 `candidate-only-review`。
- 每個 rule block 均記錄 current file、start／end line、selector、SHA-256、HTML／JS static hits、21 頁 runtime DOM 命中與 page／screenshot／interaction coverage。
- 分類決策為 grouped／compound 或 dynamic／status／direct-reference 的規則全部保留；未建立 deletion queue。
- runtime DOM 零命中只作觀測，不作刪除授權。

## 覆蓋與驗證

- frontend：21 頁。
- interaction：94 steps。
- `python regression/td15_remain_01_rebaseline.py --check`：`TD15_REMAIN_01_OK`。
- `python regression/td15_residual_inventory.py --check --snapshot-date 2026-09-01`：`TD15_R0_OK`。
- `python regression/td15_js_residual_audit.py --check`：`TD15_R3_OK`。
- `python -m unittest test_derivatives_platform.py`：176 tests PASS。
- `python security_guardrail_check.py`：16/16 PASS。
- `python e2e_smoke.py`：`E2E_SMOKE_OK`。
- `python regression/td18_shadow_verify.py`：`H10_02_VERIFY_OK`。
- `python regression/verify_against_baseline.py --full`：`VERIFY_OK`，live API、frontend compare、interaction compare 全部 PASS。

## 安全邊界

本批未修改 CSS／HTML／baseline／SQLite／`twse-cache.json`，未刪除任何 rule block，
也未授權下一批 deletion。若未來要刪除，必須另立不超過 20 個 rule blocks 的小批，
先完成人工 cascade／dynamic／responsive／state review，再執行 reverse-diff 可回復的刪除。

## Downstream closure（2026-09-01）

本 rebaseline 已由 REMAIN-04～07 完成後續使用。263 個 blocks 均有 final disposition，全部為 `retain`；沒有 deletion candidate，因此未執行 reverse diff 或 CSS 刪除。完整對帳見 `TD15_REMAIN_07_evidence_2026-09-01.md`。
