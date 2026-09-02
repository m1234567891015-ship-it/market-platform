# TD15-REMAIN-02 CSS candidate-only batch evidence

日期：2026-09-01  
狀態：✅ no-op 結案；沒有具備完整證據的安全刪除候選

## 前置條件結果

依 TD15-REMAIN-01 最新 manifest 重新核對：

- current rule blocks：263。
- current candidate names：129。
- `candidate-only-review`：0。
- `retain-grouped-or-compound-review`：65。
- `retain-dynamic-status-or-direct-reference`：198。
- `deletion_authorized`：`false`。

## 執行決策

本批原定從 `candidate-only-review` 選出不超過 20 個 rule blocks。由於目前數量為
0，沒有可安全建立的 deletion queue；grouped／compound、responsive、state、
dynamic、status 與 direct-reference 規則全部保留。本批未呼叫
`delete_css_rules.py`，未刪除 CSS，也未修改 HTML／JS／baseline／runtime data。

這不是把證據不足視為通過，而是依「證據不足即保留」規則完成 no-op 決策。未來若
現況出現新的 candidate-only blocks，必須另以 current file／line／selector／hash、
三層證據與不超過 20 blocks 的獨立批次重新審查。

## 驗證

- `python regression/td15_residual_inventory.py --check --snapshot-date 2026-09-01`：
  `TD15_R0_OK`。
- `python regression/td15_remain_01_rebaseline.py --check`：
  `TD15_REMAIN_01_OK`，21 頁／94 steps runtime evidence 可重現。
- `python regression/td15_js_residual_audit.py --check`：`TD15_R3_OK`。
- 目前工作樹既有 gate：176 unit tests、security 16/16、E2E、TD18 shadow、94/94
  interaction 與 full baseline 均已通過；本批沒有 source／CSS 變更可造成其結果漂移。

本批未 commit。

## Final status（2026-09-01）

REMAIN-04～07 已完成後續全量 review 與 closure。REMAIN-07 對帳 263/263 blocks，全部 `retain`，delete candidate=0、blocked=0；本批 no-op closure 未執行 CSS 刪除。
