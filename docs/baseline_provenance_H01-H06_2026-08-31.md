# H-01～H-06 Baseline 來源追溯

本文件補記目前工作樹中 baseline 差異的來源證據。結論分成「已由批次紀錄／git history 證實」與「目前只能確認存在、尚不足以歸屬」兩類；不以目前的檔案狀態反推未記錄的批次來源。

## 已證實來源

| Baseline 檔案 | 差異 | 可追溯批次 | 證據 |
|---|---|---|---|
| `regression/baseline/frontend/global_symbols.json` | 移除 14 個已確認死碼 global symbols | H-04-11～H-04-15 | 主計畫 H-04-11～H-04-15 明載每批移除相應 JS 死碼並同步更新 global-symbol baseline；git history 對應 `1214071`、`0e62c49`、`fd7e521`。 |
| `regression/baseline/escapehtml_baseline.json` | `escapeHtml_call_count` `1905 → 1887` | H-04-13～H-04-15 | 主計畫 H-04-13、H-04-14、H-04-15 明載分段由 `1905→1904→1895→1887`，並同步更新 baseline；git history 對應同一組 TD-15 commits。 |

## 已確認存在、但 H-01～H-06 尚無足夠歸屬證據

| Baseline 檔案 | 目前差異 | 現有證據判定 |
|---|---|---|
| `regression/baseline/frontend_manifest.json` | `derivatives-assets.html` 的 `cards` `31 → 32` | H-01 明載未更新 screenshot；H-02 明載未更新 frontend manifest；H-03、H-05、H-06 也明載未更新 baseline。現有文件與 git history 未提供 H-01～H-06 的對應 commit。 |
| `regression/baseline/screenshots/derivatives-ai.html.png` | binary diff，`1,352,833 → 1,358,535` bytes | 目前只能確認 binary 差異；H-01、H-02、H-03、H-05、H-06 的批次紀錄沒有宣告此截圖更新，也沒有對應 commit。 |
| `regression/baseline/screenshots/derivatives-analytics.html.png` | binary diff，`1,343,843 → 1,349,601` bytes | 同上；不能只依檔名把它歸到某個 H 批次。 |
| `regression/baseline/screenshots/derivatives-assets.html.png` | binary diff，`2,112,675 → 2,186,183` bytes | 同上；目前工作樹另有 derivatives 頁面 nav-links 差異，但沒有批次紀錄證明這些截圖就是由 H-01～H-06 產生。 |

## H-01～H-06 的排除證據

- H-01：明載「未更新任何 screenshot、API 或 interaction baseline」。
- H-02：明載「未更新 screenshot、API、frontend manifest 或 interaction baseline」。
- H-03：各子批次明載「未更新任何 baseline」。
- H-04：明確更新的是 TD-15 死碼移除所需的 global-symbol／escapeHtml baseline；其餘 H-04 子批次明載未更新 baseline。
- H-05：各子批次明載未更新 baseline。
- H-06：明載不更新 screenshot／interaction baseline，且 H-06-01～H-06-04 均未執行 bundler、HTML 或產品行為變更。

## 後續處理

1. `global_symbols.json` 與 `escapehtml_baseline.json` 可標記為 H-04 產物。
2. `frontend_manifest.json` 與 3 張截圖先標記「來源待補」，不得在沒有 commit／批次紀錄或人工核准前重新 capture、覆寫或納入新的 baseline commit。
3. 若確認這 4 個檔案確實屬於 H-01～H-06，需補上對應批次、變更理由、人工畫面核對與完整 verify 證據；否則應另立獨立 baseline provenance／UI 變更紀錄。
