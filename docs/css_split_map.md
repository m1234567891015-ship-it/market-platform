# CSS 拆分對照表(styles.css → css/*.css)

依 `docs/工單TD02_前端拆分.md` 裁決 Q5:CSS 精確拆分不預先一次盤點,
每批搬移當下才對該批涉及的規則現查現核對,累積記錄於本文件。

## 方法與安全性質

- **拆分單位**:以 `styles.css` 的頂層規則區塊(單一 selector 群組或
  `@media`/`@keyframes` 等 at-rule 區塊)為最小搬移單位,由
  `regression/move_css_batch.py` 以區塊在目前 `styles.css` 中的起始行號
  (`startLine`)辨識、擷取、搬移,不逐字重打(避免轉譯風險,比照
  `regression/move_frontend_batch.py` 對 JS 的作法)。
- **逐位元組驗證**:每批搬移後,用 `regression/verify_css_split_bytes.py`
  比對搬移前 `styles.css`(指定 git ref)與搬移後目標檔案,確認每個區塊
  位元組完全一致。
- **分類依據**:沿用 `docs/frontend_module_map.md` 第 6 節的 class 前綴統計
  表,將前綴對應到與 JS 模組同名的 CSS 檔案。前綴不屬於任何已知類別的
  區塊(標記 `UNMATCHED`)暫留在 `styles.css`,留到後續批次視情況歸類或
  併入最終的共用/未分類檔案。
- **bond-/precious-metal- 命名決策**(依使用者指示):這兩個資產類別沒有
  獨立前綴,樣式併在 `asset-finance-` 命名空間下,因此併入
  `css/page-global-market-assethub.css`,跟 JS 側
  `page-global-market-assethub.js` 的分類一致。
- **CSS 屬於「行為變更」風險等級高於 JS 搬移**:JS 只有「頂層立即執行碼
  不可引用尚未載入模組」這個順序限制(函式本體因為呼叫時機在所有腳本
  載入完成後,不受宣告順序影響);但 CSS 的 cascade 是純粹依「文件順序」
  排優先序(同 specificity 時後者覆蓋前者)。把散落在原始檔案各處的
  同前綴規則搬到同一個獨立檔案,必然改變它們跟「留在 styles.css 裡、
  原本前後夾雜的其他規則」之間的相對順序——這個重排無法完全避免
  (除非放棄語意分類、改採純位置切割,但那樣就無法對齊 JS 模組結構)。
  **因此每批搬移後,以 `verify_against_baseline.py --full` 的 21 頁
  pixel diff 作為主要把關手段**,而非假設「相同前綴規則之間沒有
  specificity 衝突」就當作已充分驗證。若 pixel diff 出現差異,視為
  該批次失敗,檢查衝突規則後調整(例如該規則改標記為 SHARED 或維持
  原位)再重跑,不放行帶著已知視覺差異的批次。
- **載入順序慣例**:延續 JS 拆分的慣例——已抽出的模組檔案(`css/*.css`)
  在每個 HTML 頁面中都排在 `styles.css` 的 `<link>` 標籤**之前**,
  `styles.css` 本身扮演「尚未歸類/共用基底」的角色,隨批次進行持續縮小,
  跟 JS 那邊 `app.js` 最後留下 bootstrap 尾端的角色類比(最後才載入,
  但因為 CSS 没有 JS 那種函式呼叫依賴,這裡"最後載入"純粹是延續同一個
  慣例,不是功能性依賴)。

## 批次紀錄

| 批次 | 目標檔案 | 區塊數 | 前綴/選擇器 | 對應 JS 模組 | 備註 |
|---|---|---|---|---|---|
| CSS-1 | `css/charts.css` | 37 | `chart-`(含少量巢狀的 `.ma-color`、`.is-*` 修飾類別、以及一條 `.derivatives-overview-card-head .chart-subtitle` 巢狀覆寫規則,均以最右側/關鍵選擇器 `chart-*` 判定歸屬) | `js/charts.js` | 全部單一目標,無需人工排除;含 3 條 `.technical-volume-bar.*` 巢狀規則,判定為 chart 元件的內部覆寫,留在 charts.css |

## 尚未歸類前綴(留待後續批次)

| 前綴 | 粗估出現次數(依 frontend_module_map.md) | 預定目標 |
|---|---|---|
| `asset-finance-`/`asset-hub-`/`derivatives-`/`bond-`/`precious-metal-` | 722+104+300+0+0 | `css/page-global-market-assethub.css` |
| `options-` | 518 | `css/page-global-market-options.css` |
| `futures-` | 431 | `css/page-global-market-futures.css` |
| `sector-`/`watchlist-`/`tw-etf-` | 230+60+47 | `css/page-tw.css` |
| `us-etf-`/`us-watchlist-`/`us-stock-` | 143+11 | `css/page-us.css` |
| `stock-detail-` | 3 | `css/stock-detail.css` |
| `technical-`/`institution-`/`backtest-`/`vix-`/`portfolio-` | 72+118+101+73+52 | 跨頁共用,個別核對後決定去向(可能落在對應頁面模組或建立共用檔) |
| `nav-` | 11 | `css/components.css` |
| 無法辨識前綴(UNMATCHED,約 1225 個頂層區塊) | - | 留在 `styles.css`,待各批次搬移完成後視剩餘內容決定是否需要 `css/legacy-unclassified.css` 或維持在 `styles.css` 作為共用基底 |
