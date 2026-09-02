# TD15-REMAIN-01 CSS manifest rebaseline（2026-09-01）

本批只重建現況 manifest 與三層證據，不刪除 CSS、不更新 baseline、不授權 deletion。

## 結論

- 狀態：`TD15_REMAIN_01_PASS_NO_DELETION`。現況 263 個 rule blocks、129 個候選名稱。
- 分類決策：`retain-grouped-or-compound-review` 65、`retain-dynamic-status-or-direct-reference` 198、`candidate-only-review` 0。
- Runtime DOM 觀測：28 個候選名稱在頁面命中、101 個未命中；未命中不等於可刪除。
- 行為範圍：21 頁、94 條 interaction steps、同等 screenshot manifest 覆蓋。

## 三層證據

每個 rule block 均保留 current file／startLine／endLine／selector／SHA-256；並嵌入 candidate class 的 HTML／JS static hits、21 頁 runtime DOM 命中與 21 頁／94 steps screenshot／interaction coverage。

- grouped／compound、responsive、state、dynamic、status 或 direct-reference 規則維持保留決策。
- candidate-only blocks 目前為 0；沒有形成可刪除 queue。
- runtime DOM 零命中只記錄觀測結果，不作為刪除證據；未來若要刪除仍須人工核對 cascade 與所有入口。

## 護欄

本批 `deletion_authorized=false`、`baseline_changed=false`。既有 21 頁、94 條互動、security／CSP、API 與 pixel 驗證另由專案既有 gate 執行；任何未分類差異都必須停止後續 deletion batch。

完整逐 rule-block machine-readable evidence 見同名 JSON。

## Downstream closure（2026-09-01）

REMAIN-04～07 已在本 rebaseline 上完成 263 個 blocks 的逐項 review 與 closure。最終 disposition 為 `retain=263`、`observe=0`、`delete_candidate=0`、`blocked=0`；未執行新的 CSS 刪除。詳見 `TD15_REMAIN_07_evidence_2026-09-01.md`。
