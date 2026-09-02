# CSS 未使用規則掃描報告

依 `docs/工單TD02_前端拆分.md` 第 8 節「明確排除項」第 2 點:未使用 CSS
規則**只掃描、產出報告,不刪除**。刪除屬行為變更,需另行確認、走另一張
工單。本報告不修改任何檔案。

## 更正記錄(TD-15 執行第一層/第三層刪除時發現,回頭補記於此)

1. **候選 ID 全數為擷取邏輯誤判,實際不存在**:本報告原列出的 7 個候選
   ID(`options-online`/`options-regional`/`sector-sync`/`us-search`/
   `us-sector-stock`/`us-stock`/`weighted-index`)經 TD-15 重新以兩種
   獨立方法核實,在目前的 `split-*.css` 全文中都找不到任何一個作為真正
   ID 選擇器存在——例如 `sector-sync` 實際只以更長的 `#sector-sync-view`
   存在。這 7 個從未真實存在,不是「未使用」而是「原本就不是獨立 ID」,
   詳見 `docs/td15_css_classification.md`。
2. **字串掃描範圍遺漏根目錄下 4 個獨立腳本檔案**:本報告第 2 節寫的
   掃描範圍「全部 `js/*.js` + `app.js`」實際上遺漏了 `pwa.js`、
   `derivatives-ui.js`、`service-worker.js`、`twse-data.js` 這 4 個
   根目錄下的獨立腳本(它們不在 `js/*.js` 這個 glob pattern 內,也不是
   `app.js`)。TD-15 執行刪除時,批次 4 的 21 頁 pixel diff 抓到
   `pwa-controls`/`pwa-network` 這兩個 class 實際在 `pwa.js` 裡有真實
   引用(PWA 安裝/連線狀態元件),是本報告的偽陽性。已用這 4 個檔案
   重新核對本報告列出的全部 135 個高信心候選,確認只有這 2 個受影響,
   詳見 `docs/td15_css_classification.md`。

## 方法

1. 從 `split-01.css` ~ `split-07.css`(拆分後的 7 個檔案,`styles.css`
   本身已是空殼)的每個頂層規則(含 `@media`/`@supports` 內的巢狀規則,
   排除 `@keyframes`/`@font-face` 內部的關鍵影格/字型描述,那些不是
   selector)取出 selector 標頭,解析出所有 class(`.foo`)與
   ID(`#foo`)選擇器名稱。**只掃描選擇器標頭,不掃描宣告內容**——
   第一版嘗試曾誤把 `#a8492a` 這類十六進位色碼當成 ID 選擇器,已修正。
2. 對每個選擇器名稱,在全部 21 個 `*.html` 與全部 `js/*.js` + `app.js`
   原始碼中做「文字邊界比對」(前後不能緊接 `[_a-zA-Z0-9-]` 字元,避免
   `us-stock` 誤配到 `us-stocks.html` 這種子字串)。完全沒有比對到的
   名稱列為「候選未使用」。
3. **已知的偽陽性類別**:JS 端有不少 class 是用樣板字面值動態組出來的
   (例如 `` `chart-ma-line ma-${series.period}` ``),這種名稱在原始碼
   裡永遠不會以完整字面文字出現,純文字比對抓不到「有在用」。本報告
   額外掃描 JS 原始碼裡 `` 前綴-${...} `` 這種樣式,抓出已知會動態組合
   的字首清單(見下),候選未使用清單裡凡是以這些字首開頭的,標記為
   「高機率偽陽性」,跟其餘候選分開列,但**兩份清單都需要人工複查**,
   本報告的分類只是信心分級,不是最終判定。

## 已知動態組合字首(高機率偽陽性,共 81 個候選命中)

`asset-`、`asset-finance-trend-`、`bond-`、`institution-card-`、`is-`、
`is-line-`、`ma-`、`market-ai-risk-`、`market-risk-`、`market-sector-`、
`metric-`、`option-region-`、`other-`、`sector-`、`us-market-ranking-`

已人工核實的例子:`ma-5`/`ma-10`/`ma-20`/`ma-60`/`ma-120`/`ma-240` 全部
落在候選清單裡,但 `js/charts.js:473` 有
`` `<path class="chart-ma-line ma-${series.period}" ...>` ``,`
js/page-global-market-futures.js:3840` 與 `js/page-us.js:2469` 也有
`` `<i class="ma-color ma-${period}"></i>` ``——這 6 個是確認的偽陽性,
不是死碼。`is-` 開頭的候選(如 `is-benchmark`、`is-panic`、`is-red` 等
色調/狀態修飾類別)也高度疑似是類似模式,但沒有逐一人工核實每一條。

**這個字首清單是啟發式的,不是精確判定**——尤其 `asset-`/`sector-`
字首範圍較廣,不排除誤傘蓋到真正未使用的規則。人工複查時仍應對這
81 條逐一確認,不能直接假設「有標記就是有在用」。

## 候選未使用清單

### 高信心候選(135 個 class,不落在已知動態字首內)

已抽樣核實 3 條(`chart-area`、`chart-points`、`chart-stack`)在任何
`*.html`/`js/*.js`/`app.js` 都零命中,包含子字串比對也是零——這 3 條
較有把握是真正的死 CSS(可能是舊版圖表實作留下的)。其餘 132 條未逐一
人工核實,僅為文字掃描結果。

```
backtest-benchmark-card, backtest-factor-list, backtest-learning-summary,
backtest-signal, backtest-signal-list, chart-area, chart-points,
chart-stack, chip-price-area, chip-summary-card, chip-summary-grid,
class-hero-main, class-hero-metrics, class-hero-value-row,
derivatives-overview-hot-strikes, derivatives-overview-indicator-grid,
derivatives-overview-intelligence-grid, derivatives-overview-macro-grid,
derivatives-overview-position-card, derivatives-overview-section-head,
derivatives-overview-signal, derivatives-overview-signal-copy,
derivatives-overview-signal-section, derivatives-overview-technical-card,
detail-grid, detail-link, futures-analysis-visual,
futures-center-region-summary, futures-snapshot-axis,
futures-snapshot-bar, futures-snapshot-chart, futures-snapshot-date,
futures-snapshot-distribution, futures-snapshot-distribution-head,
futures-snapshot-divider, futures-snapshot-grid, futures-snapshot-line,
futures-snapshot-point, futures-snapshot-rank-bar,
futures-snapshot-rank-list, futures-snapshot-rank-no,
futures-snapshot-rank-row, futures-snapshot-rank-symbol,
futures-snapshot-readout, futures-timeframe-chip, ghost-link,
index-comparison-grid, index-comparison-insight, insight-list,
institutional-coverage-note, institutional-drift-list,
legend-swatch-ma, legend-swatch-strength, limit-move-card,
margin-balance-item, margin-balance-list, margin-balance-title,
margin-balance-track, options-decision-factor-block, options-heat-cell,
options-heat-table, options-heatmap-layout, options-heatmap-side,
options-market-chain-data-table, options-market-chain-data-wrap,
options-market-chain-row-button, options-oi-heatmap,
options-region-factor-block, penny-trend-metrics, pwa-action,
pwa-controls, pwa-network, pwa-update, stock-table, table-head,
table-row, taiex-vix-trading-card, taiex-vix-trading-summary,
taiex-vix-trading-table, trend-tab, trend-tabs, tw-etf-list-head,
us-agent-row, us-architecture-card, us-architecture-grid,
us-architecture-node, us-architecture-title, us-engine-row,
us-etf-category-filters, us-etf-dashboard, us-etf-detail-badges,
us-etf-detail-body, us-etf-detail-brief, us-etf-detail-chart-panel,
us-etf-detail-facts, us-etf-detail-hero, us-etf-detail-signal-grid,
us-etf-detail-watchlist, us-etf-entry-card, us-etf-entry-tags,
us-node-number, us-search-detail-card, us-search-facts,
us-search-panel, us-search-suggestion, us-search-suggestions,
us-sector-alpha-area, us-sector-alpha-bars, us-sector-alpha-line,
us-sector-base-line, us-sector-benchmark-line,
us-sector-chart-stat-strip, us-sector-end-label, us-sector-focus-line,
us-sector-plain-result, us-sector-relative-band, us-sector-stock-item,
us-sector-volume-bars, us-watchlist-actions, us-watchlist-card,
vix-card, vix-meta-list, vix-mini-chart, vix-mini-chart-wrap,
vix-signal-badge, vix-signal-head, vix-signal-panel, vix-stale-note,
vix-updated, vix-value, vix-value-row, weighted-index-note-card,
weighted-index-summary-row, weighted-vix-analysis-card, wide
```

### 高機率偽陽性(81 個 class,落在已知動態字首內,詳見上一節)

```
asset-finance-bond-detail-layout, asset-finance-bond-map-list,
asset-finance-bond-online-card, asset-finance-bond-rating-list,
asset-finance-dashboard-layout, asset-finance-driver-notes,
asset-metal-ratio-card, is-alt, is-benchmark, is-blue, is-calm,
is-compare, is-current, is-cyan, is-dashboard, is-dealer, is-good,
is-green, is-hedge, is-high, is-institution-daily, is-lagging,
is-leader, is-leading, is-margin-daily, is-margin-overview,
is-max-pain, is-models, is-normal, is-offline, is-orange, is-panic,
is-previous, is-purple, is-ratio, is-red, is-region-factors, is-risk,
is-rotation, is-tight, is-total, is-trust, is-warn, is-yellow, ma-10,
ma-120, ma-20, ma-240, ma-5, ma-60, market-ai-risk-high,
market-ai-risk-low, market-ai-risk-medium, market-risk-high,
market-risk-low, market-risk-medium, metric-band, metric-high,
metric-low, metric-open, metric-pct, metric-previous, metric-price,
metric-risk-temp, metric-sentiment, metric-vix-level, metric-volume,
sector-card, sector-card-main, sector-card-side, sector-diff-marker,
sector-difference-bar, sector-ma-line, sector-relative-band,
sector-signal-dot, sector-strength-area, sector-strength-line,
sector-strength-zero, sector-sync-side-card, sector-sync-stat-card,
sector-time-band
```

### 候選未使用 ID(7 個,均不落在動態字首範圍,信心相對高)

```
options-online, options-regional, sector-sync, us-search,
us-sector-stock, us-stock, weighted-index
```

已人工核實 `us-search`/`us-sector-stock`/`weighted-index`/`sector-sync`
這 4 個:HTML/JS 裡都只找到「更長的字尾變體」(如
`us-search-results`、`us-sector-stock-table`、
`weighted-index-panel`、`sector-sync-view`),沒有精確符合這個短
ID 本身的 `getElementById`/`id="..."` 用法,判斷為真正未被引用的
ID 選擇器(可能是重構過程中 ID 改長名但 CSS 沒同步清掉)。
`options-online`/`options-regional` 完全零命中,同樣未人工進一步
追查。

## 統計總覽

| 項目 | 數量 |
|---|---|
| 掃描到的 class 選擇器總數 | 1,456 |
| 掃描到的 ID 選擇器總數 | 13 |
| 候選未使用 class(合計) | 216 |
| ↳ 高信心候選 | 135 |
| ↳ 高機率偽陽性(動態組合字首) | 81 |
| 候選未使用 ID | 7 |

## 結論與後續建議

本報告**只掃描,未刪除任何規則**,符合工單第 8 節要求。清單僅供後續
另立工單(需使用者明確確認)參考,不可直接依此清單刪除——尤其
「高信心候選」也只是文字掃描結果,實際仍可能有本報告方法論漏抓的
動態組合模式(例如透過陣列/物件查表而非樣板字面值組出的 class 名),
需要逐條人工核對對應頁面實際渲染路徑後才能判定是否真的是死 CSS。
