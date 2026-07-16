# Market Pulse V1.0 R6 — 技術債稽核清單

來源:`MarketPulse_技術債稽核_2026-07-16.xlsx`(market-platform-Backup_1_.zip 的 2026-07-12 快照,稽核日期 2026-07-16)

## 債項清單

| ID | 嚴重度 | 類別 | 債項 | 位置(檔案:行號) | 影響 | 建議修法 | 預估工時 | 優先序 |
|---|---|---|---|---|---|---|---|---|
| TD-01 | 高 | 架構 | 後端巨石復發:app.py 單檔 15,513 行,475 函式、48 routes | app.py 全檔 | 任何修改都在 70 萬字元的檔案內進行,merge 衝突與回歸風險極高;先前 AST 模組化成果已流失 | 重啟模組化:routes / fetchers / builders / cache / security 分層拆分,以先前的 SPEC.md + AST 工具流程執行 | 5-8天 | 1 |
| TD-02 | 高 | 架構 | 前端巨石:app.js 單檔 34,149 行、單一 IIFE、824 函式,無模組系統 | app.js 全檔 | 無法 tree-shake、無法單元測試個別模組;每頁載入 1.8MB | 導入 ES modules + 打包(esbuild/Vite),按頁面路由做 code splitting | 5-8天 | 2 |
| TD-03 | 高 | 正確性 | 記憶體狀態與多 worker 部署衝突:rate limit state、快取、in-flight 鎖皆為模組層 dict | app.py L525(rate limiter)、mutable state ×4、locks ×8 | gunicorn 開多 worker 時 rate limiting 失效、快取不一致、冷快取鎖僅單進程有效——隱性正確性 bug | 短期:Procfile 明文鎖定 --workers 1;長期:rate limit / 快取狀態外移至 SQLite 表或 Redis | 1天/3-5天 | 3 |
| TD-04 | 高 | 版控 | 無版本控制:備份 zip 內無 .git,且混包 60MB SQLite + 2.2MB twse-cache.json | derivatives-platform.sqlite3、twse-cache.json | 無法 diff、無法回溯單一變更;程式碼與執行期資料無法分離交付 | 建 git repo、.gitignore 排除 *.sqlite3 / *cache.json;資料檔移至 data/ 目錄並於 README 標註 | 0.5天 | 4 |
| TD-05 | 高 | 重複 | 重複程式碼約 19.5%(前後端相同比例);86 個 fetch_* 函式高度樣板化 | app.py(fetch_* ×86、build_* ×95) | 新增資料來源需複製整段樣板;修一個 header/timeout 邏輯要改數十處 | 抽象統一 fetcher 層:source registry(URL、headers、parser、TTL 宣告式設定)+ 單一 HTTP client | 3-5天 | 5 |
| TD-06 | 中 | 複雜度 | 超長函式:enforce_api_rate_limit 385 行,另有 7 個 ≥150 行函式(見「大型函式」表) | app.py L525 等 | 單函式承擔限流、身分識別、視窗管理、清理多職責,難以測試 | 按職責拆分:identity / window / eviction / response 各自成函式 | 1-2天 | 6 |
| TD-07 | 中 | 安全 | SSL unverified fallback 仍存在:smart.tdcc.com.tw 於非 production 直接跳過驗證;non-production 自動允許 fallback | app.py L1369、L1392(_urlopen_with_ssl_fallback) | 開發機環境變數誤設即靜默降級;allowlist 有 12 個 host 範圍偏大 | 改為 opt-in 白名單逐 host 授權 + 每次 fallback 強制記錄;評估以 certifi bundle 補齊 TDCC 憑證鏈 | 0.5-1天 | 7 |
| TD-08 | 中 | 重複 | 21 個 HTML 頁面存在 10 種 `<nav>` 變體(含 1 頁無 nav) | 各 *.html(見「Nav 分歧」表) | 導覽列改一個連結需同步 9+ 處;derivatives-ai.html 為孤兒頁不載入共用資源 | nav 抽成單一來源:由 app.js 注入或 build script 產生;修復 derivatives-ai.html | 1天 | 8 |
| TD-09 | 中 | 效能 | 每頁全量載入 app.js 1.8MB + styles.css 447KB,無 minify/split;service worker 快取已停用(CACHE_VERSION=disabled、fetch passthrough) | service-worker.js、各 *.html | 行動端每頁全量下載;PWA 離線能力名存實亡 | 重新啟用 SW 並採 stale-while-revalidate 靜態資源策略;搭配 TD-02 code splitting | 1-2天 | 9 |
| TD-10 | 中 | 測試 | 測試量 42 個 unit tests 對 15,513 行後端,關鍵 builder/fetcher 覆蓋結構性不足 | test_derivatives_platform.py | 重構(TD-01/05)缺乏安全網 | 重構前先為 top-10 大型函式補特性測試(golden file / fixture 比對) | 2-3天 | 10 |
| TD-11 | 低 | 品質 | app.js 出現兩個同名 function worker(後者遮蔽前者) | app.js L8738、L22560 | IIFE 作用域內重名,實際行為依定義順序,屬地雷 | 重新命名並確認兩處呼叫點 | 0.5天 | 11 |
| TD-12 | 低 | 品質 | 快取設定發散:25 個 *_CACHE_* TTL 常數散落各處,無統一快取抽象、幾乎無 eviction | 見「快取與鎖」表 | 記憶體僅增不減(bounded 僅 1 處);TTL 語意不一致 | 併入 TD-05 fetcher 層:宣告式 TTL + 上限 LRU | 併入TD-05 | 12 |
| TD-13 | 低 | 品質 | Python 檔混入 CRLF 行尾;broad except Exception 約 150 處(多數有 log/fallback,少數靜默) | app.py(try ×241、except Exception ×154) | 跨平台 diff 噪音;個別靜默 except 吞錯 | .gitattributes 統一 LF;為靜默 except 補 LOGGER.debug 最低限度記錄 | 0.5天 | 13 |

## 總覽

| 指標 | 數值 | 說明 |
|---|---|---|
| app.py 行數 | 15514 | 475 函式 \| 48 routes \| fetch_*×86 \| build_*×95 |
| app.js 行數 | 34150 | 824 函式 \| 單一 IIFE \| 無 import/export |
| styles.css 行數 | 21973 | 約 3,605 條規則 |
| 重複程式碼比例(app.py) | 0.195 | 以 ≥40 字元行重複估計 |
| 重複程式碼比例(app.js) | 0.196 | 同上 |
| SQLite 資料庫(混包) | 60.7 MB | options_quote 110,080 筆 |
| twse-cache.json(混包) | 2.1 MB | 執行期快取不應入包 |
| 模組層鎖數量 | 8 | 單進程假設,見 TD-03 |
| 快取 TTL 常數 | 25 | 無統一快取層,見 TD-12 |
| unit tests | 42 | 另有 e2e_smoke / fixtures / release integrity(正面) |

債項數(依嚴重度):高 5 件、中 5 件、低 3 件。

## 超長函式清單(重構優先標的)

| 檔案 | 函式 | 行數 | 起始行 | 建議 |
|---|---|---|---|---|
| app.py | enforce_api_rate_limit | 385 | L525 | 按職責拆分 |
| app.py | build_stock_detail | 304 | L8677 | 按職責拆分 |
| app.py | build_analysis_sections | 290 | L8233 | 按職責拆分 |
| app.py | build_sector_fund_flow | 246 | L4847 | 抽出子步驟 |
| app.py | build_site_data | 207 | L9158 | 抽出子步驟 |
| app.py | build_news | 177 | L8981 | 抽出子步驟 |
| app.py | build_live_sector_site_data | 162 | L9660 | 抽出子步驟 |
| app.py | fetch_yahoo_margin_trading | 159 | L6041 | 抽出子步驟 |
| app.js | renderStockDetail | 2376 | L30029 | 拆分為渲染/資料/事件模組 |
| app.js | analyzeTechnicalTheories | 826 | L7424 | 拆分為渲染/資料/事件模組 |
| app.js | renderUsDetailAnalysisCards | 486 | L20885 | 拆分為渲染/資料/事件模組 |
| app.js | renderTechnicalChart | 409 | L29620 | 拆分為渲染/資料/事件模組 |
| app.js | buildInstitutionalBacktestFramework | 308 | L6669 | 拆分為渲染/資料/事件模組 |
| app.js | buildBacktestLearningModel | 305 | L6364 | 拆分為渲染/資料/事件模組 |
| app.js | renderAssetFinanceDecisionCenterPanel | 298 | L25126 | 拆分為渲染/資料/事件模組 |
| app.js | renderFuturesInvestmentFramework | 271 | L13755 | 拆分為渲染/資料/事件模組 |
| app.js | renderAssetFinanceBondSingleAnalysis | 265 | L25914 | 拆分為渲染/資料/事件模組 |
| app.js | renderDerivativesMarketOverview | 238 | L28488 | 拆分為渲染/資料/事件模組 |
| app.js | buildWeightedSectorTrendModels | 217 | L3285 | 拆分為渲染/資料/事件模組 |
| app.js | renderAssetFinanceMetalDriversPanel | 215 | L24911 | 拆分為渲染/資料/事件模組 |
| app.js | buildMarketAiInsightModel | 207 | L4700 | 拆分為渲染/資料/事件模組 |

## 記憶體狀態盤點(TD-03 / TD-12 佐證)

| 類型 | 名稱 | 行號 | 備註 |
|---|---|---|---|
| TTL 常數 | BUNDLED_CACHE_FILE | L101 | `BASE_DIR / "twse-cache.json"` |
| TTL 常數 | CACHE_FILE | L102 | `Path(os.environ.get("MARKET_PULSE_CACHE_FILE", str(BUNDLED_CACHE_FILE)))` |
| TTL 常數 | CACHE_VERSION | L111 | 13 |
| TTL 常數 | SECTOR_CHART_CACHE_SECONDS | L117 | 300 |
| TTL 常數 | EXTERNAL_TEXT_CACHE_SECONDS | L127 | 5 * 60 |
| TTL 常數 | GLOBAL_MARKET_ITEM_CACHE_SECONDS | L128 | 5 * 60 |
| TTL 常數 | TREASURY_YIELD_CURVE_CACHE_SECONDS | L129 | 6 * 60 * 60 |
| TTL 常數 | US_OPTIONS_CHAIN_CACHE_SECONDS | L130 | 5 * 60 |
| TTL 常數 | YAHOO_TW_STOCK_RESOURCE_CACHE_SECONDS | L131 | 5 * 60 |
| TTL 常數 | TWSE_COMPANY_INDUSTRY_CACHE_SECONDS | L132 | 12 * 60 * 60 |
| TTL 常數 | SECTOR_FUND_FLOW_CACHE_SECONDS | L133 | 10 * 60 |
| TTL 常數 | PUBLIC_CACHE_ERROR_MESSAGE | L457 | "背景資料更新暫時無法完成,請稍後再試" |
| TTL 常數 | CACHE_FLIGHT_WAIT_SECONDS | L556 | 120 |
| TTL 常數 | PENNY_SECTOR_RECOMMENDATION_CACHE_SECONDS | L561 | 30 * 60 |
| TTL 常數 | TAIFEX_UNDERLYING_LIST_CACHE_SECONDS | L582 | 6 * 60 * 60 |
| TTL 常數 | TAIFEX_STOCK_DERIVATIVE_AGGREGATE_CACHE_SECONDS | L583 | 15 * 60 |
| TTL 常數 | TAIFEX_INSTITUTION_DETAIL_CACHE_SECONDS | L584 | 15 * 60 |
| TTL 常數 | YAHOO_TW_FUTURE_CACHE_SECONDS | L603 | 60 |
| TTL 常數 | YAHOO_TW_OPTION_CACHE_SECONDS | L606 | 60 |
| TTL 常數 | YAHOO_OPTIONS_CHAIN_CACHE_SECONDS | L854 | 5 * 60 |
| TTL 常數 | YAHOO_OPTIONS_CRUMB_CACHE_SECONDS | L855 | 45 * 60 |
| TTL 常數 | BARCHART_OPTIONS_CHAIN_CACHE_SECONDS | L858 | 5 * 60 |
| TTL 常數 | DERIBIT_OPTIONS_CHAIN_CACHE_SECONDS | L890 | 60 |
| TTL 常數 | BYBIT_OPTIONS_CHAIN_CACHE_SECONDS | L898 | 60 |
| TTL 常數 | US_ETF_CENTER_CACHE_SECONDS | L13684 | 5 * 60 |
| threading.Lock | API_RATE_LIMIT_LOCK | L455 | 單進程有效;多 worker 下失去保護 |
| threading.Lock | cache_lock | L552 | 單進程有效;多 worker 下失去保護 |
| threading.Lock | cache_refresh_lock | L553 | 單進程有效;多 worker 下失去保護 |
| threading.Lock | cache_flight_lock | L554 | 單進程有效;多 worker 下失去保護 |
| threading.Lock | background_updater_lock | L557 | 單進程有效;多 worker 下失去保護 |
| threading.Lock | penny_sector_recommendation_lock | L559 | 單進程有效;多 worker 下失去保護 |
| threading.Lock | taifex_options_chain_inflight_lock | L574 | 單進程有效;多 worker 下失去保護 |
| threading.Lock | _verified_ssl_context_lock | L1323 | 單進程有效;多 worker 下失去保護 |
| 模組層可變狀態 | API_RATE_LIMIT_STATE | L453 | 多 worker 下各進程獨立副本 |
| 模組層可變狀態 | cache_flights | L555 | 多 worker 下各進程獨立副本 |
| 模組層可變狀態 | penny_sector_recommendation_cache | L560 | 多 worker 下各進程獨立副本 |
| 模組層可變狀態 | taifex_options_chain_inflight | L573 | 多 worker 下各進程獨立副本 |

## HTML 導覽列變體分佈(TD-08 佐證)

| HTML 檔案 | `<nav>` 指紋(MD5 前 8 碼) | 群組 |
|---|---|---|
| bonds.html | 8597066e | 變體 3 |
| derivatives-ai.html | (無 nav) | 無 nav |
| derivatives-analytics.html | bcc04ef3 | 變體 5 |
| derivatives-assets.html | 6908a393 | 變體 6 |
| derivatives-status.html | abca2509 | 變體 7 |
| futures.html | 4068ec23 | 變體 1 |
| index.html | 2c752c79 | 變體 2 |
| international-finance.html | 8597066e | 變體 3 |
| market-overview.html | 2c752c79 | 變體 2 |
| news.html | 2c752c79 | 變體 2 |
| options.html | fe5bcb31 | 變體 8 |
| precious-metals.html | c9feddc6 | 變體 9 |
| tw-Optional-stocks.html | 2c752c79 | 變體 2 |
| tw-etf.html | 4068ec23 | 變體 1 |
| tw-stock-search.html | 2c752c79 | 變體 2 |
| tw-stocks.html | 2c752c79 | 變體 2 |
| us-etf.html | 4068ec23 | 變體 1 |
| us-market-overview.html | 0d693dab | 變體 10 |
| us-stock-search.html | 4068ec23 | 變體 1 |
| us-stocks.html | 4068ec23 | 變體 1 |
| us-watchlist.html | 4068ec23 | 變體 1 |

合計:21 頁 / 10 種變體。目標:1 種。

## 既有優點(重構時必須保留的資產)

| 項目 | 證據 | 重構注意事項 |
|---|---|---|
| SQL 全參數化,零字串拼接 | app.py execute() 掃描 0 處 f-string/concat | fetcher 層重構時維持 parameterized 慣例 |
| CSP 嚴格 | script-src 'self'、frame-ancestors 'none'(app.py L504 起) | 導入 bundler 後勿為方便加回 unsafe-inline |
| XSS 防護系統化 | escapeHtml() 呼叫 2,037 次;innerHTML 138 處均經審核 | 拆分 app.js 時 escapeHtml 保持單一來源 |
| 無 hardcoded secrets、debug=False | app.py L15506 | — |
| 低依賴 | requirements.txt 僅 Flask/gunicorn/certifi | fetcher 重構可考慮續用 stdlib urllib 維持零新增依賴 |
| 測試基礎設施存在 | e2e_smoke.py、TAIFEX/TWSE fixtures、verify_release_integrity.py | 以 fixtures 為基礎擴充特性測試(TD-10) |
| 安全標頭完整 | X-Frame-Options、HSTS、nosniff、Permissions-Policy | — |
| SSL fallback 有 production 阻擋與 allowlist | `_urlopen_with_ssl_fallback` 設計上已有 gating | TD-07 為收緊而非重寫 |
