# TD-15 CSS 選擇器分類表(第一輪)

候選清單來源:`docs/css_unused_report.md`(216 個候選 class + 7 個候選 ID)。

**重要更正(ID 候選)**:本次重新逐一核實 `docs/css_unused_report.md` 列出的 7 個候選 ID
(`options-online`/`options-regional`/`sector-sync`/`us-search`/`us-sector-stock`/
`us-stock`/`weighted-index`),用兩種獨立方法(逐一 grep + 重新以 parse_blocks 解析)在
目前的 `split-*.css` 全文中**都找不到任何一個作為真正 ID 選擇器存在**——例如 `sector-sync`
實際只以 `#sector-sync-view`（更長的 ID）出現,原報告的擷取邏輯有誤將其誤判為獨立候選。
這 7 個 ID **不存在於當前 CSS,無從刪起**,予以排除,不列入本表刪除候選,已在
`docs/css_unused_report.md` 的後續使用中應視為已知錯誤修正。

**重要更正(grouped selector 安全性,執行刪除前發現並修正)**:準備第四部分實際刪除時,
發現本表最初的「動態拼接判定」/「引用掃描」只逐一檢查每個候選 class 本身,沒有檢查
「同一條規則的其他逗號分支選擇器是否也全部是死 class」。CSS 規則可以用逗號分組多個
選擇器共用一個宣告區塊(例如 `.mini-list.wide, .detail-metrics, .table-head, .table-row,
.history-row, .analysis-grid { ... }`),若只因為其中一個分支(`.table-head`)是死 class
就整條規則刪除,會連帶刪掉其他活著的分支(`.detail-metrics`/`.analysis-grid` 等)的樣式,
屬於「誤刪」。修正後的判定標準:**一條規則要安全可刪,規則內所有逗號分支引用的 class
必須全部落在死碼候選清單內,缺一都整條規則降級為不刪**。修正後,以下 12 個 class 原本
標記可刪,重新核實後**查無任何 100% 純淨(不牽連其他存活 class)的出現位置**,改為
本輪不刪:`class-hero-main`、`derivatives-overview-hot-strikes`、
`derivatives-overview-indicator-grid`、`derivatives-overview-position-card`、
`derivatives-overview-technical-card`、`limit-move-card`、`us-etf-dashboard`、
`us-etf-detail-watchlist`、`us-sector-alpha-bars`、`us-sector-volume-bars`、
`weighted-index-note-card`、`wide`。另有 104 個規則區塊(對應到其餘 123 個仍可刪除的
class 之外的其他出現位置)因牽連其他存活 class 而不刪除,只刪除那些「規則整體 100%
純淨」的出現位置——這代表部分可刪 class 的某些出現位置會保留、不會被完全清除,是
「寧可漏刪」原則下刻意的保守選擇。

**重要更正(掃描範圍遺漏根目錄 JS 檔,執行第四批次時經 pixel diff 抓到)**:批次 4
刪除後,`verify --full` 的 21 頁 pixel diff 出現 5 頁超過 2% 差異門檻(derivatives-status.html/
tw-Optional-stocks.html/tw-stock-search.html/us-stock-search.html/us-watchlist.html)。
追查發現:本表(以及最早的 `docs/css_unused_report.md`)從頭到尾的字串掃描範圍都只有
`js/*.js` + `app.js`,**遺漏了根目錄下另外 4 個獨立腳本檔案**:`pwa.js`(PWA 安裝/連線
狀態元件)、`derivatives-ui.js`、`service-worker.js`、`twse-data.js`。用這 4 個檔案重新
比對全部 135 個原始候選,發現 `pwa-controls`/`pwa-network` 確實在 `pwa.js`
(第 29/32/41 行)有真實引用——這是本輪唯一受影響的 2 個 class(其餘 133 個候選逐一
比對後在這 4 個檔案裡皆零命中,包含批次 1-3 已刪除的 60 個,已個別核實過,那 60 個
乾淨無誤,不需回退)。`pwa-controls`/`pwa-network` 改列本輪不刪,批次 4 重新執行時
排除這兩個(見下方表格判定欄)。**後續所有批次的掃描範圍已擴大為
`js/*.js` + `app.js` + `pwa.js` + `derivatives-ui.js` + `service-worker.js` + `twse-data.js`**。

## 方法

1. **靜態引用掃描**:沿用 `css_unused_report.md` 的文字邊界比對結果(已排除子字串誤配)。
2. **動態拼接判定**:掃描全部 `js/*.js` + `app.js` + `pwa.js` + `derivatives-ui.js` +
   `service-worker.js` + `twse-data.js` 是否有 ``前綴-${...}`` 樣板字面值組合模式
   (找到 15 個動態字首,見 `css_unused_report.md`),額外掃描 `'字串' + 變數`
   字串串接與 `classList.add(變數)` 純變數呼叫兩種模式(**本輪掃描結果:皆無新增命中**)。
3. **語義狀態詞排除**(工單第 3 部分第四節要求):候選 class 若語意上關聯資料狀態
   (如 `-up`/`-down`/`-alert`/`-warning` 等色調字尾),即使靜態掃描判定為死也一律
   降級不刪。對 135 個高信心候選逐一比對常見狀態字尾樣式,**本輪掃描結果:無命中**
   (135 個候選都是結構性版面 class,如 `-grid`/`-card`/`-table`/`-panel`,非狀態語意)。

## Class 分類表(216 個)

| 選擇器 | 出現於 | 動態拼接 | 判定 | 依據 |
|---|---|---|---|---|
| `.asset-finance-bond-detail-layout` | split-06.css:2926; split-06.css:2933; split-07.css:351 等共4處 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.asset-finance-bond-map-list` | split-06.css:2801; split-06.css:2941; split-06.css:2947 等共8處 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.asset-finance-bond-online-card` | split-06.css:2152 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.asset-finance-bond-rating-list` | split-06.css:2801; split-06.css:2941; split-06.css:2951 等共5處 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.asset-finance-dashboard-layout` | split-06.css:770; split-07.css:351; split-07.css:564 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.asset-finance-driver-notes` | split-06.css:997; split-06.css:1008; split-06.css:1499 等共8處 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.asset-metal-ratio-card` | split-05.css:1385; split-05.css:1602; split-05.css:1613 等共5處 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.backtest-benchmark-card` | split-02.css:1798; split-02.css:1808; split-02.css:1813 等共4處 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.backtest-factor-list` | split-02.css:1791; split-02.css:1995 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.backtest-learning-summary` | split-02.css:1769; split-02.css:1777; split-02.css:1781 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.backtest-signal` | split-02.css:2025; split-02.css:2032; split-02.css:2038 等共4處 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.backtest-signal-list` | split-02.css:2018; split-03.css:1971 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.chart-area` | split-02.css:3271 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.chart-points` | split-02.css:3287 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.chart-stack` | split-02.css:2897 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.chip-price-area` | split-03.css:348 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.chip-summary-card` | split-03.css:85; split-03.css:97; split-03.css:101 等共8處 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.chip-summary-grid` | split-03.css:47; split-03.css:78; split-03.css:2299 等共5處 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.class-hero-main` | split-01.css:2839 | 是(grouped selector) | 本輪不刪 | 所有安全候選出現位置皆屬 grouped selector,牽連其他非死碼 class,整條規則不能整段刪除;查無 100% 純淨出現位置 |
| `.class-hero-metrics` | split-01.css:2862; split-03.css:1938 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.class-hero-value-row` | split-01.css:2844; split-01.css:2852; split-01.css:2857 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.derivatives-overview-hot-strikes` | split-04.css:2952; split-04.css:2965; split-04.css:2975 等共6處 | 是(grouped selector) | 本輪不刪 | 所有安全候選出現位置皆屬 grouped selector,牽連其他非死碼 class,整條規則不能整段刪除;查無 100% 純淨出現位置 |
| `.derivatives-overview-indicator-grid` | split-04.css:2945; split-04.css:2952; split-04.css:2965 等共8處 | 是(grouped selector) | 本輪不刪 | 所有安全候選出現位置皆屬 grouped selector,牽連其他非死碼 class,整條規則不能整段刪除;查無 100% 純淨出現位置 |
| `.derivatives-overview-intelligence-grid` | split-04.css:2931; split-04.css:3489; split-05.css:26 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.derivatives-overview-macro-grid` | split-04.css:3077; split-05.css:26 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.derivatives-overview-position-card` | split-04.css:2938 | 是(grouped selector) | 本輪不刪 | 所有安全候選出現位置皆屬 grouped selector,牽連其他非死碼 class,整條規則不能整段刪除;查無 100% 純淨出現位置 |
| `.derivatives-overview-section-head` | split-04.css:2918; split-04.css:2926; split-05.css:55 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.derivatives-overview-signal` | split-04.css:2623; split-04.css:2633; split-04.css:2634 等共4處 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.derivatives-overview-signal-copy` | split-04.css:2757; split-04.css:2763; split-04.css:2769 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.derivatives-overview-signal-section` | split-04.css:2619 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.derivatives-overview-technical-card` | split-04.css:2938 | 是(grouped selector) | 本輪不刪 | 所有安全候選出現位置皆屬 grouped selector,牽連其他非死碼 class,整條規則不能整段刪除;查無 100% 純淨出現位置 |
| `.detail-grid` | split-01.css:233; split-01.css:3105; split-03.css:1772 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.detail-link` | split-03.css:2190 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.futures-analysis-visual` | split-04.css:555 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.futures-center-region-summary` | split-05.css:539 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.futures-snapshot-axis` | split-04.css:1107 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.futures-snapshot-bar` | split-04.css:1107; split-04.css:1134; split-04.css:1138 等共4處 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.futures-snapshot-chart` | split-04.css:185; split-04.css:194 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.futures-snapshot-date` | split-04.css:1107; split-04.css:1115 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.futures-snapshot-distribution` | split-04.css:971 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.futures-snapshot-distribution-head` | split-04.css:944; split-04.css:982; split-04.css:989 等共5處 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.futures-snapshot-divider` | split-04.css:1097; split-04.css:1103 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.futures-snapshot-grid` | split-04.css:1097 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.futures-snapshot-line` | split-04.css:1119 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.futures-snapshot-point` | split-04.css:1128 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.futures-snapshot-rank-bar` | split-04.css:1064; split-04.css:1072; split-04.css:1080 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.futures-snapshot-rank-list` | split-04.css:1005 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.futures-snapshot-rank-no` | split-04.css:1027; split-04.css:1039 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.futures-snapshot-rank-row` | split-04.css:1010; split-04.css:1022; split-04.css:1039 等共7處 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.futures-snapshot-rank-symbol` | split-04.css:1044; split-04.css:1050; split-04.css:1055 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.futures-snapshot-readout` | split-04.css:928; split-04.css:934; split-04.css:944 等共5處 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.futures-timeframe-chip` | split-04.css:437; split-04.css:451 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.ghost-link` | split-04.css:1621; split-04.css:1630; split-04.css:1630 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.index-comparison-grid` | split-01.css:1726; split-01.css:1733; split-01.css:1742 等共4處 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.index-comparison-insight` | split-01.css:1718 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.insight-list` | split-01.css:157; split-01.css:3125; split-01.css:3130 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.institutional-coverage-note` | split-02.css:1536 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.institutional-drift-list` | split-02.css:1513; split-02.css:1519; split-02.css:1532 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.is-alt` | split-01.css:2497 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.is-benchmark` | split-03.css:3204 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.is-blue` | split-03.css:2604; split-04.css:1283; split-04.css:1450 等共5處 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.is-calm` | split-03.css:2881 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.is-compare` | split-05.css:151 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.is-current` | split-03.css:952; split-03.css:956 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.is-cyan` | split-04.css:1288; split-04.css:1455 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.is-dashboard` | split-05.css:150 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.is-dealer` | split-03.css:336; split-03.css:545; split-03.css:1548 等共4處 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.is-good` | split-05.css:1977 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.is-green` | split-01.css:1822; split-01.css:1873; split-01.css:1908 等共16處 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.is-hedge` | split-01.css:3272 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.is-high` | split-03.css:2890 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.is-institution-daily` | split-03.css:1053 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.is-lagging` | split-03.css:3050; split-03.css:3094; split-03.css:3200 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.is-leader` | split-01.css:1512 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.is-leading` | split-03.css:3045; split-03.css:3090; split-03.css:3196 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.is-margin-daily` | split-03.css:1058 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.is-margin-overview` | split-03.css:1063 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.is-max-pain` | split-05.css:2602 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.is-models` | split-05.css:2066; split-07.css:512 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.is-normal` | split-03.css:2881 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.is-offline` | split-04.css:2551 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.is-orange` | split-04.css:1285; split-04.css:1452; split-05.css:1987 等共6處 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.is-panic` | split-03.css:2894 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.is-previous` | split-03.css:948 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.is-purple` | split-01.css:1834; split-01.css:1885; split-01.css:1923 等共9處 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.is-ratio` | split-03.css:476; split-03.css:538 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.is-red` | split-01.css:1830; split-01.css:1881; split-01.css:1918 等共16處 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.is-region-factors` | split-05.css:3095 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.is-risk` | split-01.css:1522 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.is-rotation` | split-01.css:1517 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.is-tight` | split-06.css:2666 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.is-total` | split-03.css:1552 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.is-trust` | split-03.css:332; split-03.css:538; split-03.css:1544 等共4處 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.is-warn` | split-05.css:1982 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.is-yellow` | split-01.css:1826; split-01.css:1877; split-01.css:1913 等共14處 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.legend-swatch-ma` | split-01.css:2816 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.legend-swatch-strength` | split-01.css:2812 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.limit-move-card` | split-02.css:103 | 是(grouped selector) | 本輪不刪 | 所有安全候選出現位置皆屬 grouped selector,牽連其他非死碼 class,整條規則不能整段刪除;查無 100% 純淨出現位置 |
| `.ma-10` | split-02.css:3300; split-02.css:3300 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.ma-120` | split-02.css:3306; split-02.css:3306 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.ma-20` | split-02.css:3302; split-02.css:3302 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.ma-240` | split-02.css:3308; split-02.css:3308 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.ma-5` | split-02.css:3298; split-02.css:3298 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.ma-60` | split-02.css:3304; split-02.css:3304 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.margin-balance-item` | split-03.css:913; split-03.css:956; split-03.css:960 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.margin-balance-list` | split-03.css:551 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.margin-balance-title` | split-03.css:918; split-03.css:927; split-03.css:931 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.margin-balance-track` | split-03.css:935; split-03.css:942; split-03.css:948 等共5處 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.market-ai-risk-high` | split-01.css:3164 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.market-ai-risk-low` | split-01.css:3174 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.market-ai-risk-medium` | split-01.css:3169 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.market-risk-high` | split-01.css:3341; split-01.css:3378; split-01.css:3478 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.market-risk-low` | split-01.css:3353; split-01.css:3388; split-01.css:3482 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.market-risk-medium` | split-01.css:3347; split-01.css:3383 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.metric-band` | split-01.css:1197 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.metric-high` | split-01.css:1165; split-03.css:1743 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.metric-low` | split-01.css:1165; split-03.css:1743 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.metric-open` | split-01.css:1165; split-03.css:1743 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.metric-pct` | split-01.css:1165; split-01.css:1183; split-03.css:1743 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.metric-previous` | split-01.css:1165; split-03.css:1743 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.metric-price` | split-01.css:1165; split-01.css:1178; split-01.css:1183 等共4處 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.metric-risk-temp` | split-01.css:1197 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.metric-sentiment` | split-01.css:1197 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.metric-vix-level` | split-01.css:1197 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.metric-volume` | split-01.css:1174; split-03.css:1752 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.options-decision-factor-block` | split-05.css:3108; split-05.css:3182 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.options-heat-cell` | split-05.css:2606; split-05.css:2616; split-05.css:2620 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.options-heat-table` | split-05.css:2593; split-05.css:2597; split-05.css:2597 等共4處 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.options-heatmap-layout` | split-05.css:2586; split-07.css:351; split-07.css:474 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.options-heatmap-side` | split-05.css:2530; split-05.css:2543; split-05.css:2554 等共7處 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.options-market-chain-data-table` | split-06.css:277; split-06.css:281 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.options-market-chain-data-wrap` | split-06.css:272 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.options-market-chain-row-button` | split-06.css:285; split-06.css:296; split-06.css:296 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.options-oi-heatmap` | split-05.css:2576 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.options-region-factor-block` | split-05.css:3099 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.penny-trend-metrics` | split-01.css:703; split-01.css:742; split-01.css:752 等共8處 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.pwa-action` | split-04.css:2514 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.pwa-controls` | split-04.css:2498; split-04.css:2596 | 是(pwa.js,原掃描範圍遺漏此檔) | 不刪(第一輪誤判,已更正) | 見下方「掃描範圍更正」說明 |
| `.pwa-network` | split-04.css:2532; split-04.css:2543; split-04.css:2551 等共5處 | 是(pwa.js,原掃描範圍遺漏此檔) | 不刪(第一輪誤判,已更正) | 見下方「掃描範圍更正」說明 |
| `.pwa-update` | split-04.css:2527 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.sector-card` | split-01.css:157; split-01.css:874; split-01.css:3051 等共5處 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.sector-card-main` | split-01.css:3058 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.sector-card-side` | split-01.css:3062; split-01.css:3070; split-01.css:3074 等共5處 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.sector-diff-marker` | split-01.css:2661; split-01.css:2665 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.sector-difference-bar` | split-01.css:2529; split-01.css:2535; split-01.css:2539 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.sector-ma-line` | split-01.css:2595 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.sector-relative-band` | split-01.css:2524 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.sector-signal-dot` | split-01.css:2605; split-01.css:2610; split-01.css:2614 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.sector-strength-area` | split-01.css:2571 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.sector-strength-line` | split-01.css:2562 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.sector-strength-zero` | split-01.css:2543 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.sector-sync-side-card` | split-01.css:1080; split-01.css:2310 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.sector-sync-stat-card` | split-01.css:2147; split-01.css:2156; split-01.css:2161 等共5處 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.sector-time-band` | split-01.css:2493; split-01.css:2497 | 是(樣板字面值字首比對命中) | 不刪(動態組合類) | 見 css_unused_report.md 已知動態字首清單,本輪不再重複刪除評估 |
| `.stock-table` | split-01.css:61; split-01.css:3083 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.table-head` | split-01.css:3087; split-01.css:3096; split-03.css:2263 等共4處 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.table-row` | split-01.css:3087; split-01.css:3101; split-03.css:2263 等共4處 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.taiex-vix-trading-card` | split-01.css:1666; split-01.css:1676 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.taiex-vix-trading-summary` | split-01.css:1680; split-01.css:1686; split-01.css:1694 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.taiex-vix-trading-table` | split-01.css:1686; split-01.css:1694; split-01.css:1694 等共6處 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.trend-tab` | split-01.css:2882; split-01.css:2893 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.trend-tabs` | split-01.css:2876; split-03.css:2249 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.tw-etf-list-head` | split-02.css:1035 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.us-agent-row` | split-04.css:1322 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.us-architecture-card` | split-04.css:1202 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.us-architecture-grid` | split-04.css:1227 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.us-architecture-node` | split-04.css:1233; split-04.css:1247; split-04.css:1247 等共13處 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.us-architecture-title` | split-04.css:1211; split-04.css:1215; split-04.css:1221 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.us-engine-row` | split-04.css:1291; split-04.css:1300; split-04.css:1306 等共4處 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.us-etf-category-filters` | split-04.css:1748; split-04.css:1755; split-04.css:1760 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.us-etf-dashboard` | split-04.css:2112 | 是(grouped selector) | 本輪不刪 | 所有安全候選出現位置皆屬 grouped selector,牽連其他非死碼 class,整條規則不能整段刪除;查無 100% 純淨出現位置 |
| `.us-etf-detail-badges` | split-04.css:1957; split-04.css:1964; split-04.css:2476 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.us-etf-detail-body` | split-04.css:2013; split-04.css:2411 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.us-etf-detail-brief` | split-04.css:2064; split-04.css:2411 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.us-etf-detail-chart-panel` | split-04.css:2020; split-04.css:2029; split-04.css:2033 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.us-etf-detail-facts` | split-04.css:2037; split-04.css:2043; split-04.css:2053 等共6處 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.us-etf-detail-hero` | split-04.css:1936; split-04.css:1944; split-04.css:1950 等共4處 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.us-etf-detail-signal-grid` | split-04.css:1968; split-04.css:2416; split-04.css:2470 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.us-etf-detail-watchlist` | split-04.css:2020; split-04.css:2087; split-04.css:2092 | 是(grouped selector) | 本輪不刪 | 所有安全候選出現位置皆屬 grouped selector,牽連其他非死碼 class,整條規則不能整段刪除;查無 100% 純淨出現位置 |
| `.us-etf-entry-card` | split-04.css:2130; split-04.css:2330 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.us-etf-entry-tags` | split-04.css:2139; split-04.css:2213; split-04.css:2213 等共8處 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.us-node-number` | split-04.css:1254 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.us-search-detail-card` | split-04.css:1538 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.us-search-facts` | split-04.css:1639; split-04.css:2424 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.us-search-panel` | split-04.css:1493 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.us-search-suggestion` | split-04.css:1504; split-04.css:1517; split-04.css:1517 等共7處 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.us-search-suggestions` | split-04.css:1498 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.us-sector-alpha-area` | split-03.css:3086; split-03.css:3090; split-03.css:3094 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.us-sector-alpha-bars` | split-03.css:3107; split-03.css:3111 | 是(grouped selector) | 本輪不刪 | 所有安全候選出現位置皆屬 grouped selector,牽連其他非死碼 class,整條規則不能整段刪除;查無 100% 純淨出現位置 |
| `.us-sector-alpha-line` | split-03.css:3098 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.us-sector-base-line` | split-03.css:3080 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.us-sector-benchmark-line` | split-03.css:3028 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.us-sector-chart-stat-strip` | split-03.css:3154; split-03.css:3160; split-03.css:3172 等共5處 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.us-sector-end-label` | 刪除前 `split-03.css:2998,3002,3006` | 否 | ✅ H-09-03 已刪除(3 rule blocks) | 刪除前完整 HTML／JS 零命中；實際產生的是 `sector-end-label`，非 `us-sector-end-label`；無 shared live branch、media 或 responsive 依賴 |
| `.us-sector-focus-line` | split-03.css:3036; split-03.css:3045; split-03.css:3050 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.us-sector-plain-result` | split-03.css:3125; split-03.css:3134; split-03.css:3139 等共5處 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.us-sector-relative-band` | split-03.css:3059; split-03.css:3063; split-03.css:3067 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.us-sector-stock-item` | split-03.css:3282; split-03.css:3287 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.us-sector-volume-bars` | split-03.css:3071; split-03.css:3071; split-03.css:3076 | 是(grouped selector) | 本輪不刪 | 所有安全候選出現位置皆屬 grouped selector,牽連其他非死碼 class,整條規則不能整段刪除;查無 100% 純淨出現位置 |
| `.us-watchlist-actions` | split-04.css:1614 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.us-watchlist-card` | split-04.css:1598; split-04.css:1609 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.vix-card` | split-02.css:3414 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.vix-meta-list` | split-02.css:3457 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.vix-mini-chart` | split-02.css:3451 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.vix-mini-chart-wrap` | split-02.css:3444 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.vix-signal-badge` | split-01.css:1865; split-01.css:1873; split-01.css:1877 等共5處 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.vix-signal-head` | split-01.css:1852; split-01.css:1859 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.vix-signal-panel` | split-01.css:1843 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.vix-stale-note` | split-02.css:3472 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.vix-updated` | split-02.css:3467 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.vix-value` | split-02.css:3425; split-02.css:3433; split-02.css:3434 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.vix-value-row` | split-02.css:3418 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.weighted-index-note-card` | split-01.css:1258 | 是(grouped selector) | 本輪不刪 | 所有安全候選出現位置皆屬 grouped selector,牽連其他非死碼 class,整條規則不能整段刪除;查無 100% 純淨出現位置 |
| `.weighted-index-summary-row` | split-01.css:1109; split-01.css:1116; split-01.css:1123 等共5處 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.weighted-vix-analysis-card` | split-01.css:1722 | 否 | 第三層(可刪) | 純文字掃描全 repo 零命中,非已知動態字首,非語義狀態詞 |
| `.wide` | split-01.css:312; split-03.css:2263; split-03.css:2365 | 是(grouped selector) | 本輪不刪 | 所有安全候選出現位置皆屬 grouped selector,牽連其他非死碼 class,整條規則不能整段刪除;查無 100% 純淨出現位置 |

## ID 候選:全數排除(不存在於當前 CSS,見上方更正說明)

| 候選 ID | 核實結果 |
|---|---|
| `#options-online` | 目前 split-*.css 全文找不到任何獨立存在的 `#options-online` 選擇器,排除 |
| `#options-regional` | 目前 split-*.css 全文找不到任何獨立存在的 `#options-regional` 選擇器,排除 |
| `#sector-sync` | 目前 split-*.css 全文找不到任何獨立存在的 `#sector-sync` 選擇器,排除 |
| `#us-search` | 目前 split-*.css 全文找不到任何獨立存在的 `#us-search` 選擇器,排除 |
| `#us-sector-stock` | 目前 split-*.css 全文找不到任何獨立存在的 `#us-sector-stock` 選擇器,排除 |
| `#us-stock` | 目前 split-*.css 全文找不到任何獨立存在的 `#us-stock` 選擇器,排除 |
| `#weighted-index` | 目前 split-*.css 全文找不到任何獨立存在的 `#weighted-index` 選擇器,排除 |

## 統計

- 第三層(可刪候選 class,grouped selector 安全性複查 + 掃描範圍擴大複查通過):
  **121 個**(原 135 個,12 個因 grouped selector 全數牽連存活 class 降級,
  2 個 `pwa-controls`/`pwa-network` 因掃描範圍遺漏 `pwa.js` 誤判,兩項更正
  見上方說明)
- 本輪不刪(grouped selector 牽連其他存活 class,查無純淨出現位置):12 個
- 本輪不刪(掃描範圍遺漏根目錄 JS 檔案導致誤判,實際有真實引用):2 個(`pwa-controls`/`pwa-network`)
- 不刪(動態組合類 class):81 個
- ID 候選:0 個(原 7 個皆非真實存在的選擇器,已排除)
- 合計掃描:216 個 class + 7 個(已排除)ID
- 實際可執行刪除的規則區塊數:220(121 個 class 的所有「規則整體 100% 純淨」出現位置;
  部分 class 有多個出現位置,其中混有 grouped selector 的位置不刪,只刪純淨位置)

## H-09-01 動態候選重新核實(2026-08-31)

本批依授權只做分類與證據對帳,未修改任何 `split-*.css` 規則。掃描輸入固定為
`split-*.css`、21 個頁面 HTML、`app.js`、`js/*.js` 與根目錄 4 個獨立 JS
(`pwa.js`、`derivatives-ui.js`、`service-worker.js`、`twse-data.js`),並以候選 class
逐項做靜態完整字串比對，再對動態樣板、`classList` 狀態切換與頁面 manifest 交叉核實。

### 動態／組合證據矩陣

| 候選群 | 候選數 | 產生路徑／靜態結果 | 本批分類 |
|---|---:|---|---|
| `is-*` | 37 | 多個 render template 使用 `is-${...}`，例如 `stock-detail.js:268,740,824,1351`、`render-shared.js:859`、`page-global-market-futures.js:205,1880,2113`；另有 `pwa.js:44` 的 `is-offline` 及 `classList.toggle("is-active"/"is-disabled")` 狀態路徑。候選值來自 item key、tone、risk 或頁面狀態，不能以 CSS 靜態零命中判死。 | **保留(已確認動態／狀態組合)** |
| `ma-*` | 6 | `charts.js:388` 使用 `ma-${series.period}`，`stock-detail.js:2284` 使用 `ma-${period}`；可接受週期集合在 `stock-detail.js:205` 與 `page-global-market-futures.js:3712` 為 `5/10/20/60/120/240`，正好覆蓋本表 6 個候選。 | **保留(已確認動態組合)** |
| `metric-*` | 11 | `page-tw.js:2618` 使用 `metric-${metric.key}`；`page-tw.js:1548-1551` 的 metrics key 包含 `sentiment`、`vix-level`、`band`、`risk-temp`，其餘 key 亦由同一 metrics render path 產生。 | **保留(已確認動態組合)** |
| `market-ai-risk-*` | 3 | `page-global-market-options.js:3242-3252` 將 `riskTone` 限定為 `high/medium/low`，並產生 `market-ai-risk-${riskTone}`，覆蓋本表 3 個候選。 | **保留(已確認動態組合)** |
| `market-risk-*` | 3 | `page-global-market-options.js:3290-3390` 使用相同的 `high/medium/low` tone 產生 `market-risk-${riskTone}`，覆蓋本表 3 個候選。 | **保留(已確認動態組合)** |
| `sector-card` | 1 | `page-home.js:317` 有候選字串的直接 HTML template 引用。這不是 dead CSS 的純靜態零引用。 | **保留(已確認 HTML 產生路徑)** |
| `asset-*` | 7 | 全 repo HTML／JS 以候選完整字串比對均無命中；目前只有 `asset-` 前綴樣板命中，尚未找到能產生這 7 個精確 selector 的路徑。 | **保留(證據不足，待後續批次)** |
| 其餘 `sector-*` | 13 | 全 repo HTML／JS 以候選完整字串比對均無命中；目前只有 `sector-` 前綴或相鄰 static class 命中，尚未找到這 13 個精確 selector 的產生路徑。 | **保留(證據不足，待後續批次)** |

矩陣合計 81 個 dynamic rows。前述 12 個 grouped-selector 候選與 `pwa-controls`／
`pwa-network` 的根目錄 JS 真實引用，沿用本文件既有「本輪不刪」分類，不重新降級或
刪除。對 `asset-*`／13 個 `sector-*`，前綴命中本身不構成刪除授權；在沒有候選
字串產生器、完整 selector cascade 與 runtime 路徑三方一致前，一律保留。

### 頁面與互動證據

- `regression/baseline/frontend_manifest.json`：`page_count=21`，21 個 HTML 的載入／
  render snapshot 清單完整存在。
- `regression/baseline/interactions/manifest.json`：`page_count=21`、
  `step_count_total=94`；包含可操作頁面的互動路徑與 render-only 頁面覆核。
- H-09-01 不將基準檔當作修改目標；後續完整驗證只比對現況與既有基準，pixel／
  interaction 差異不得以更新 baseline 掩蓋。

### 本批結論

81 個 dynamic rows 全數列為保留，未產生任何 CSS deletion candidate。H-09-02 已另行完成
grouped selector 的 cascade／media／active／focus 細查；H-09-03 才能在三方證據一致
且另獲授權時刪除單一候選組。這次沒有修改 baseline、CSP、部署設定、SQLite 或
`twse-cache.json`。

## H-09-02 Grouped selector 逐組核實(2026-08-31)

本批重新以目前磁碟上的 `split-01.css`～`split-07.css` 解析 rule blocks；不採用舊行號
直接推定現況，也不執行 CSS 刪除。以本表 216 個 class candidates 做完整 selector
比對後，得到 247 個含候選 class 的 rule blocks：其中 188 個是 mixed grouped／
compound blocks(至少有一個非候選 class branch 或同一 compound selector 仍依賴其他
class)，59 個只有候選 class。188 個 mixed blocks 涉及 107 個候選 class，16 個位於
8 種 responsive `@media` 條件，13 個含 `:hover`／`:focus-visible`／`.is-active` 等
互動或 active 狀態。所有 mixed blocks 均保留；59 個 candidate-only blocks 也只記為
待 H-09-03 三方證據核准，不在本批刪除。

### 12 個全數降級候選逐組結果

| 候選組 | 目前 rule block | shared／狀態／responsive 依賴 | 分類 |
|---|---|---|---|
| `wide` | `split-01.css:312`；`split-03.css:40008,42344` | 與 `.mini-list`、`.detail-metrics`、`.table-head`、`.table-row`、`.history-row`、`.analysis-grid` 共用；後兩處位於 `@media (max-width: 820px/560px)`。 | **保留**：不能移除 `.wide` 而破壞窄版 layout 或其他 live class。 |
| `weighted-index-note-card` | `split-01.css:1200` | 與 `.weighted-index-note-card-inline` 共用同一宣告區塊。 | **保留**：shared branch 未被本候選涵蓋。 |
| `class-hero-main` | `split-01.css:2675` | 與 `.class-board-head h3` 共用。 | **保留**：同一 rule 仍服務 live heading。 |
| `limit-move-card` | `split-02.css:103` | 與 `.market-extreme-card` 共用。 | **保留**：共用卡片樣式不可整條移除。 |
| `us-sector-volume-bars` | `split-03.css:2944,2949` | 與 `.is-positive`／`.is-negative` 狀態 branch 共用，分別控制正負成交量色彩。 | **保留**：active／tone 狀態不可視為 dead layout。 |
| `us-sector-alpha-bars` | `split-03.css:2964,2968` | 與 `rect.is-positive`／`rect.is-negative` 狀態 branch 共用。 | **保留**：正負狀態 cascade 仍有依賴。 |
| `us-etf-dashboard` | `split-04.css:1637` | 與 `.us-module-card` compound selector 共用。 | **保留**：移除會改變 live module card 的樣式。 |
| `us-etf-detail-watchlist` | `split-04.css:1577,1612,1617` | `1577` 與 `.us-etf-detail-chart-panel`、`.us-etf-detail-brief-card` 共用；`1612/1617` 分別與 `.us-etf-detail-brief-card b/p` 共用。 | **保留**：shared detail／brief branches 仍存活。 |
| `derivatives-overview-position-card` | `split-04.css:2377` | 與 `.derivatives-overview-technical-card`、`.derivatives-overview-decision-card`、`.derivatives-overview-context-card` 共用。 | **保留**：同一宣告區塊涵蓋多個 derivatives card。 |
| `derivatives-overview-technical-card` | `split-04.css:2377` | 與 position／decision／context card 共用同一 rule。 | **保留**：不能只移除其中一個 branch。 |
| `derivatives-overview-indicator-grid` | `split-04.css:2384,2391,2404,2414,2436,2439`；`split-05.css:1077` | 與 exposure／timeframe／hot-strikes／institution／levels／news grid 共用；`2436/2439` 還含 `.is-up`／`.is-down` tone；`split-05.css:1077` 在 `@media (max-width: 520px)`。 | **保留**：shared grid、tone 與 responsive cascade 均未拆分。 |
| `derivatives-overview-hot-strikes` | `split-04.css:2391,2404,2414,2424,2443`；`split-05.css:1077` | 與 indicator／timeframe／institution／levels／news grid 共用；`split-05.css:1077` 為 responsive override。 | **保留**：刪除會連帶改變其他 derivatives overview 區塊。 |

### Mixed grouped blocks 的共通判定

- `split-01.css` 47、`split-02.css` 9、`split-03.css` 39、`split-04.css` 38、
  `split-05.css` 44、`split-06.css` 4、`split-07.css` 7 個 mixed blocks 均保留；
  其中 responsive blocks 分布為 `split-03.css` 7、`split-04.css` 1、
  `split-05.css` 3、`split-07.css` 5。
- 互動／狀態 selector 已逐一標記：`split-01.css:1615,1755,1760,1765,1770,2694`、
  `split-04.css:902,908,918,931,935,1789`、`split-06.css:2124`。這些包含
  `.is-active`、`:hover`、`:focus-visible` 或 active row 的宣告，保留 cascade，不納入
  dead CSS 刪除。
- `split-03.css:40008` 與 `42344` 的 `@media` grouped rule 特別保留，因為同一窄版
  宣告同時作用於 `.mini-list.wide`、detail metrics、table 與 analysis grid；不能按
  單一候選 class 拆除。
- 分類標準維持「所有 comma branch 與 compound class 都須有獨立 dead-code 證據，且
  不涉及狀態／responsive／cascade 依賴」；任一 shared branch、狀態或 media 依賴不確定，
  即列保留。H-09-02 未產生刪除清單，H-09-03 才能另行挑選單一、證據完整的 candidate-only
  group 並執行刪除。

本批沒有修改 `split-*.css`、baseline、CSP、部署設定、SQLite 或 `twse-cache.json`。

## H-09-03 單一候選組刪除(2026-08-31)

### 刪除前三方證據

本批只選一個候選組 `us-sector-end-label`，不擴大到其他 `us-sector-*` 或 grouped
candidate。刪除前核對結果如下：

- **CSS 靜態證據**：`split-03.css` 只剩 3 個以 `.us-sector-end-label` 為 base
  selector 的 rule blocks：`2998` (`is-leading`)、`3002` (`is-lagging`)、`3006`
  (`is-benchmark`)。三者都是同一候選 base class 的 compound state 規則，沒有 comma
  shared live branch，亦不在 `@media`／responsive wrapper 中。
- **HTML／JS 產生路徑證據**：完整掃描 root HTML、`app.js`、`js/*.js` 與 4 個根目錄
  JS 後，沒有 `us-sector-end-label` 的直接或樣板產生命中；現行產生路徑為
  `sector-end-label sector-end-label-primary/benchmark` (`js/page-tw.js:328,332`、
  `js/page-global-market-futures.js:1127,1131`)，不會命中該 `us-` selector。
- **頁面／互動證據**：刪除前既有 `21` 頁 frontend 與 `94` 條 interaction baseline
  已通過 full verify；候選只存在於 CSS，未出現在現行 HTML／JS render path，因此沒有
  可由本 selector 提供樣式的 live DOM 路徑。刪除後再跑同一套 full verify 作為回歸門檻。

### 實際變更與回歸結果

- 使用 `regression/delete_css_rules.py` 精確刪除 `split-03.css` 的 3 個 rule blocks，
  未改動相鄰 `.us-sector-analysis-grid` 或其他 selector；刪除後完整 selector 搜尋
  已找不到 `us-sector-end-label`。
- 語法：`python -m py_compile app.py` PASS；全 root／`js/*.js` `node --check`
  PASS。單元測試 176 tests PASS；security 16/16 PASS；`e2e_smoke.py` 為
  `E2E_SMOKE_OK`。
- 受限環境 full verify 的 TWSE live 502 與瀏覽器 `ERR_NETWORK_ACCESS_DENIED` 已分類為
  `[外部問題]`；允許外連重跑後 `VERIFY_OK`，cached/live API、21 頁 frontend、94 條
  interaction 與 security 全部通過。未更新任何 baseline 來掩蓋差異。
- 本批只刪除上述 3 個 CSS rule blocks 並更新本分類紀錄；未修改 CSP、部署設定、SQLite
  或 `twse-cache.json`。下一組候選須另行授權與驗證。

## 2026-09-01 REMAIN closure update

本分類表的歷史分類不再直接作為刪除清單。TD15-REMAIN-04～07 已以 current file／line／selector／SHA-256 重新完成 263 個 rule blocks 的 review；最終沒有 `delete_candidate`，因此未再刪除 CSS。後續若 CSS 或頁面行為變更，須改用最新 REMAIN manifest 重新核對。
