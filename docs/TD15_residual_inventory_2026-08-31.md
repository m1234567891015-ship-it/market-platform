# TD-15 residual inventory（R0，2026-08-31）

本報告由 `regression/td15_residual_inventory.py` 重新解析目前工作樹產生。R0 只做現況盤點與歷史刪除對帳，**不刪除任何 CSS／JS，不更新 baseline**。

## 結論

- 狀態：`R0_PASS_NO_DELETION`。分類快照為 216 個 CSS class、7 個 ID；ID 候選均列為不存在的獨立 selector。
- 目前重新解析到 263 個含候選 class 的 rule blocks，涉及 129 個目前仍出現的候選名稱。
- 初步分流：`candidate-only-review` 0、`retain-grouped-or-compound-review` 65、`retain-dynamic-status-or-direct-reference` 198。這些是 R1/R2 review queue，不是刪除授權。
- 歷史 H-04-01～10 與 H-09-03 已記錄刪除 32 個 rule blocks；舊行號不可重用。
- Page／interaction scope：21 頁、94 條 interaction steps。

## 歷史批次對帳

| batch | file | blocks | selectors |
|---|---|---:|---|
| H-04-01 | `split-02.css` | 2 | `backtest-signal` |
| H-04-02 | `assets/styles.css` | 3 | `chart-stack, chart-area, chart-points` |
| H-04-03 | `assets/styles.css` | 5 | `class-hero-value-row, class-hero-metrics` |
| H-04-04 | `split-03.css` | 4 | `chip-summary-card` |
| H-04-05 | `split-04.css` | 1 | `futures-timeframe-chip` |
| H-04-06 | `split-04.css` | 7 | `us-architecture-node` |
| H-04-07 | `split-05.css` | 2 | `options-heat-cell` |
| H-04-08 | `split-06.css` | 1 | `options-market-chain-data-table` |
| H-04-09 | `split-04.css` | 2 | `us-etf-category-filters` |
| H-04-10 | `split-03.css` | 2 | `us-sector-plain-result` |
| H-09-03 | `split-03.css` | 3 | `us-sector-end-label` |

## 後續 gate

1. 先人工選定一個不超過 20 個 rule blocks 的 queue，核對 manifest 中的 current file／line／hash。
2. `candidate-only-review` 仍需補 CSS cascade、HTML／JS／Python literal、root JS dynamic pattern、responsive／state 與 21 頁／94 條證據。
3. 任何 direct reference、dynamic prefix、status marker、grouped／compound branch 或 responsive context 都保留或降級觀察。
4. 通過人工確認後才可使用 `delete_css_rules.py`；本 R0 報告本身不授權刪除。

完整 machine-readable rule-block manifest 見同名 JSON。

## 後續現況（2026-09-01）

本檔為 2026-08-31 歷史 inventory，歷史數字與分流僅供追溯。最新 2026-09-01 R0 與 REMAIN-04～07 已重新核對 263 個 current blocks，全部 final `retain`，沒有 deletion candidate；請以 `TD15_residual_inventory_2026-09-01.md` 與 `TD15_REMAIN_07_evidence_2026-09-01.md` 為現況依據。
