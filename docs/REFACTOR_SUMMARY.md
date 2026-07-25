# Market Pulse V1.0 R6 — 重構週期總結報告

封存錨點:`git tag v1.0-refactor-complete`
週期範圍:2026-07-16 ~ 2026-07-25(115 commits)
來源稽核:`docs/TD稽核清單.md`(源自 `MarketPulse_技術債稽核_2026-07-16.xlsx`)

本文件為這個重構週期的定稿存檔版總結,內容經使用者於全案人工驗收
過程中逐項確認(escapeHtml 計數來源已於封存前重新逐函式核實,見
第 5 節)。

## 1. 全部 TD 項目狀態表

| ID | 狀態 | 一句話結果 |
|---|---|---|
| TD-00 | ✅結案 | 行為基準驗證系統建立(API baseline + 前端截圖 + 安全檢查) |
| TD-00-B | ✅結案 | 前端互動行為護欄建立,21 頁 94 步驟 |
| TD-01 | ✅結案 | app.py 15,514→650 行,拆成 routes/fetchers/builders/cache/security 分層 |
| TD-02 | ✅結案 | app.js 34,150→818 行(空殼)+ js/*.js 15 檔;styles.css 21,973→1 行殼 + split-*.css 7 檔(含 TD-14) |
| TD-03 | 🟡部分完成 | 短期(Procfile `--workers 1`)已做;長期(狀態移至 SQLite/Redis)未做,`API_RATE_LIMIT_STATE` 仍是模組層 dict |
| TD-04 | ✅實質解決 | git repo 已建立(115 commits),.gitignore 排除執行期資料;建議的 `data/` 目錄重組未做(非必要,環境變數已達成同等效果) |
| TD-05 | ✅結案 | `fetch_registry.py` 宣告式 registry,86 個 fetch_* 函式全數檢視完成,12 批次 |
| TD-06 | ✅結案 | `enforce_api_rate_limit` 拆成 identity/window/eviction/response 子函式 |
| TD-07 | ✅結案 | SSL fallback 收緊為強制 opt-in、移除 TDCC 特例、log 提升為 warning,並評估 certifi 方案不可行 |
| TD-08 | ✅結案 | nav 統一單一來源,`derivatives-ai.html` 孤兒頁修復 |
| TD-09 | ✅結案 | service worker 重啟,stale-while-revalidate |
| TD-10 | ⚪未直接處理 | 無專門工單投入;unit tests 42→115 是其他工單的副產品,並非依建議的 golden-file 方法系統性補齊 |
| TD-11 | ✅實質解決 | 目前程式碼中查無任何 `worker` 重名宣告(無專門 commit,推測隨 TD-02/TD-15 一併清除) |
| TD-12 | ✅結案 | 12 個先前無上限的快取加上共用 count-capped LRU |
| TD-13 | 🟡部分完成 | CRLF 正規化(.gitattributes)已做;靜默 except 補 `LOGGER.debug` 未見專門處理 |
| TD-14 | ✅結案 | 併入 TD-02 一併拆分 |
| TD-15 | 🟡第一輪結案 | JS 52 符號刪除 + CSS 121 class 刪除,第一輪人工驗收通過;第二輪(死鏈死碼群/CSS動態81/CSS grouped 12)使用者已明確延後 |
| TD-16 | ✅結案 | 法人歷史遞迴當機:邏輯修復 + 結構防線,基準補到 94 步驟 |
| TD-17 | ✅結案 | API baseline 外部資料源不穩定:快取預熱 + `--api-live` 分離 + 失敗訊息外部/程式碼分類,故障注入驗證通過 |
| TD-18 | ⚪未來工單 | 僅在 TD-02 文件中被排除並保留為未來占位(打包/minify/code splitting),從未正式評估規模 |
| TD-19 | ⚪未來工單 | schema_diff() key 增減容忍度盲區,本週期內登記,未修 |

彙總:19 項中 ✅結案/實質解決 13 項,🟡部分完成 3 項(TD-03/TD-13/TD-15),
⚪未處理/未來工單 3 項(TD-10/TD-18/TD-19)。

## 2. 三巨石行數對照

| 檔案 | 原始(稽核當時) | 現在 | 說明 |
|---|---|---|---|
| app.py | 15,514 行 | 650 行 | 拆成 13 個核心後端模組(app.py 為薄入口 + builders/cache/derivatives_store/fetch_registry/fetchers/market_config/parsers/routes_derivatives/routes_global_market/routes_system/routes_twse/security) |
| app.js | 34,150 行 | 818 行(僅剩註解/空行,無可執行程式碼) | 拆成 js/*.js 共 15 檔,31,974 行 |
| styles.css | 21,973 行 | 1 行(空殼) | 拆成 split-01~07.css 共 7 檔,20,777 行 |

## 3. 護欄現況(四層)

1. **安全/行為不變量**(`security_guardrail_check.py`):16 項靜態檢查,含 SQL
   參數化、escapeHtml 單一定義來源、escapeHtml 呼叫次數精確計數(現況
   1,905 次)、互動基準完整性(TD-16 補的三方一致性檢查)等。
2. **API 行為基準**(`verify_against_baseline.py`):44 個端點,`--quick`
   覆蓋 40 個快取型端點(TD-17 修復:比對前先暖身快取,失敗訊息標示
   外部/程式碼),`--api-live` 覆蓋 4 個設計上永遠即時的端點
   (`live-sectors`/`live-overview`/`live-stocks`/`live-search`,
   `--full` 自動包含)。
3. **前端畫面基準**(`frontend_check.py`):21 頁截圖 pixel-diff(>2% 即
   fail)+ console 零 error。
4. **前端互動行為基準**(`interaction_check.py`,工單 00-B):21 頁、94
   步驟(P0+P1),HAR 凍結重播。

`python -m unittest test_derivatives_platform.py`:115 個 unit tests
(原始 42 個)。

## 4. 掛帳未做項目(未來若要做的進入點)

| 項目 | 進入點 | 不做的話,實際影響 |
|---|---|---|
| TD-15 第二輪 | `docs/td15_observe_list.md`(疑似死鏈死碼群 6 符號)、`docs/td15_css_classification.md`(CSS 動態組合字首 81 個候選、grouped selector 糾纏 12 個候選) | 純維護負擔(心智負擔、易誤導未來重構者),不影響現有功能正確性——這批的三份證據標準都判定「不確定,寧可保留」,不做只是留著疑似死碼,沒有已知的使用者可感知風險 |
| TD-18 | `docs/工單TD02_前端拆分.md` 第 6、8 節(排除範圍記錄處);規模/影響尚未正式評估 | 現在每頁仍下載未壓縮的 js/*.js + split-*.css 全量;沒有實際功能缺陷,純屬效能/頻寬成本,對台股使用情境(桌面為主、頁面不算巨大)影響有限 |
| TD-19 | `docs/TD稽核清單.md` TD-19 列;`regression/diffing.py::schema_diff`(第 96-100 行) | `--quick`/`--api-live` 對「關鍵回應欄位被整段刪除」這種真實回歸目前抓不到(只抓型別衝突,不抓欄位消失);已知盲區,但需要程式碼真的把欄位刪光才會踩到,不是現在進行式的問題 |

## 5. escapeHtml 計數變動核實(2037 → 1905)

封存前針對「132 次減少是否全數來自 TD-15 刪除的死碼」重新逐一核實:

- 逐一比對 TD-15 三個 JS 刪除 commit(`1214071`/`0e62c49`/`fd7e521`,共
  52 個頂層符號)的實際 diff 內容,對每個被刪除符號的移除區塊統計
  `escapeHtml(` 出現次數(而非計算行數,因為單行可能出現多次呼叫)。
- 結果:52 個被刪符號中,25 個含 escapeHtml() 呼叫,加總後恰好等於
  132 次,與基準記錄的 2037→2001→1939→1905 三段遞減完全吻合,且三個
  commit 均無任何新增的 escapeHtml( 呼叫(純刪除,無補回)。
- 逐符號清單(僅列有 escapeHtml 的 25 個):`renderGlobalTechnicalAnalysis`
  ×14、`renderUsEtfDetailSignalCard` ×3、`renderUsEtfDetailFact` ×3、
  `renderUsEtfDetailBriefCard` ×3、`renderFuturesMarketFramework` ×5、
  `renderFuturesAiModules` ×4、`renderFuturesProductMatrix` ×3、
  `renderFuturesMiniHistogram` ×1、`renderFuturesIndicatorGauge` ×1、
  `renderFuturesAnalysisMetric` ×4、`renderFuturesAdvancedTechnicalPanel`
  ×2、`renderOptionsAnalysisCenterLegacy` ×9、
  `renderOptionsPlatformConsole` ×19、`renderOptionsInsightFeed` ×1、
  `renderOptionsFocusSelector` ×6、`renderOptionsHeroMarketPanel` ×3、
  `renderOptionsCoreModelGrid` ×3、`renderOptionsDecisionBrief` ×10、
  `renderOptionsUsChainCard` ×4(即 TD-15 稽核發現的
  `[data-asset-option-underlying]` 不可達按鈕本體)、
  `renderAssetFinanceGlobalMarketPanel` ×4、`renderAssetFinanceEtfRows`
  ×5、`renderAssetFinanceSelectableEtfRows` ×7、
  `renderAssetFinanceEtfPanel` ×9、`renderAssetFinanceCompareRow` ×6、
  `renderAssetFinanceTaiwanPanel` ×3。
- 結論:132 次減少**全數**來自已確認死碼,沒有活著的呼叫被誤刪。
- `regression/baseline/escapehtml_baseline.json` 的 `escapeHtml_call_count`
  **已經是 1905**(隨 TD-15 batch 3 commit `fd7e521` 一併更新、已
  commit),本次核實未發現需要修正之處,不需另立更新 commit。

## 6. 未來工單指引

若要重啟以下任一項,直接從對應的既有文件接續,不需重新從零盤點:

- **TD-15 第二輪**:讀 `docs/td15_observe_list.md` 與
  `docs/td15_css_classification.md` 剩餘候選清單,延用同一套三方證據
  標準(寧可放過,不可誤刪)。
- **TD-18**:讀 `docs/工單TD02_前端拆分.md` 第 6、8 節理解排除脈絡,
  先補一份規模/影響評估(現有 js/*.js + split-*.css 總大小、目前無
  minify/code-splitting 對載入時間的實測影響),再決定是否立案。
- **TD-19**:讀 `docs/TD稽核清單.md` TD-19 列 + `regression/diffing.py`
  的 `schema_diff()` 現有邏輯,設計「關鍵欄位白名單」機制。

依 CLAUDE.md 規則,重啟任一項前仍須先確認是「行為不變」或「行為變更」
型工單,後者需先提案、經使用者確認才可動工。
