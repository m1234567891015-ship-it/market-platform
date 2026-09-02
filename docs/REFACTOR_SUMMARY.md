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
| TD-02 | ✅結案 | 21 頁已接上 full-site ESM loader；895-symbol bridge、classic fallback、rollback 與 browser canary 完成；原 classic source 仍保留作安全網 |
| TD-03 | 🟡部分完成／暫時封存 | 本機 Redis real probe、四條 production shared-mode paths 與雙 worker probe 已通過；正式 provider staging、觀測期、人工核准與 production rollout 仍暫停 |
| TD-04 | ✅實質解決 | git repo 已建立(115 commits),.gitignore 排除執行期資料;建議的 `data/` 目錄重組未做(非必要,環境變數已達成同等效果) |
| TD-05 | ✅結案 | `fetch_registry.py` 宣告式 registry,86 個 fetch_* 函式全數檢視完成,12 批次 |
| TD-06 | ✅結案 | `enforce_api_rate_limit` 拆成 identity/window/eviction/response 子函式 |
| TD-07 | ✅結案 | SSL fallback 收緊為強制 opt-in、移除 TDCC 特例、log 提升為 warning,並評估 certifi 方案不可行 |
| TD-08 | ✅結案 | nav 統一單一來源,`derivatives-ai.html` 孤兒頁修復 |
| TD-09 | ✅結案 | service worker 重啟,stale-while-revalidate |
| TD-10 | ✅ REMAIN-01～03 結案 | top-10 高風險 builder／fetcher 已固定離線 fixture matrix、contract tests 與正常／空資料／適用錯誤分支 |
| TD-11 | ✅實質解決 | 目前程式碼中查無任何 `worker` 重名宣告(無專門 commit,推測隨 TD-02/TD-15 一併清除) |
| TD-12 | ✅結案 | 12 個先前無上限的快取加上共用 count-capped LRU |
| TD-13 | ✅ REMAIN-01～03 結案 | 161 個 production broad exception 完成分類；靜默路徑補最低限度 logging，API log 不記錄 query value |
| TD-14 | ✅結案 | 併入 TD-02 一併拆分 |
| TD-15 | ✅review closure 完成 | TD15-REMAIN-01～07 已完成 263 個 current CSS rule blocks 的 identity／evidence／disposition；`retain=263`、`observe=0`、`delete_candidate=0`、`blocked=0`，未執行新的 CSS deletion |
| TD-16 | ✅結案 | 法人歷史遞迴當機:邏輯修復 + 結構防線,基準補到 94 步驟 |
| TD-17 | ✅結案 | API baseline 外部資料源不穩定:快取預熱 + `--api-live` 分離 + 失敗訊息外部/程式碼分類,故障注入驗證通過 |
| TD-18 | ✅ REMAIN-01～04 結案 | deterministic shadow／minify、21 頁效能量測、index／futures canary、正式 minified wiring 與 rollback package 完成；classic fallback 保留 |
| TD-19 | ✅ REMAIN-01～03 結案 | 44/44 endpoint-policy required-key 對帳、離線 fault injection、failure labels 與 quick/full verifier closure 完成 |

彙總:19 項中 ✅結案/實質解決 18 項,🟡部分完成 1 項(TD-03)。TD-02 全站 ESM、TD-10、TD-13、TD-18、TD-19 的後續批次已完成；目前僅 TD-03 Redis staging／多 worker rollout 仍暫時封存。

## 1.1 TD-15 現況更新（2026-09-01）

TD15-REMAIN-01～07 已完成 review closure。263 個 current CSS
rule blocks 全部完成 identity／evidence／disposition，最終 `retain=263`、`observe=0`、
`delete_candidate=0`、`blocked=0`。沒有安全刪除候選，因此未執行新的 CSS deletion；這是 evidence-based
closure，不是把保留中的 CSS 誤標為死碼。詳見 `docs/TD15_final_closure_2026-09-01.md`。

## 1.2 TD-10／TD-13／TD-18／TD-19 後續批次 closure（2026-09-01）

- TD-10：10/10 top-risk functions 已有 fixture／contract coverage；`test_derivatives_platform.py` 與 TD-19 offline tests 共 185 tests 通過。
- TD-13：production broad exception inventory 共 161 筆（131 direct log、25 delegated API log、5 translate/re-raise、0 未決靜默）；logging fault injection 通過且不暴露 query value。
- TD-18：固定 Node 24.18.0／Terser 5.51.2；3 bundles 與 source maps deterministic，21 頁量測完成；index 0.000%、futures 0.084% canary pixel diff，asset requests 25→10，正式 minified wiring 與 classic rollback 保留。
- TD-19：44/44 manifest endpoints 與 required-key policy 一對一；移除 required key 會以程式碼格式回歸 FAIL，null／empty 依契約容忍，error-only 與外部失敗分類保留。
- 驗證：security 16/16、`E2E_SMOKE_OK`、`VERIFY_OK`（API quick/live、21 頁 frontend、94/94 interactions）；未更新 baseline。

證據：`docs/TD10_REMAIN_01-03_evidence_2026-09-01.md`、`docs/TD13_REMAIN_01-03_evidence_2026-09-01.md`、`docs/TD18_前端打包效能評估_2026-08-31.md`、`docs/TD19_REMAIN_01-03_closure_2026-09-01.md`。

## 1.3 TD-02 全站 ESM Phase 3～4 closure（2026-09-01）

- 21/21 HTML entry 已接到 `market-pulse-esm-loader.js`，正常模式載入
  `market-pulse-esm.min.js`；full bundle 以 895-symbol transitional bridge 維持既有 owner 對帳。
- 21 頁 normal／rollback 共 42 次 browser canary 通過，包含 `derivatives-ai.html` 轉址後的 rollback
  傳遞與 `derivatives-status.html` classic addon fallback；DOM counts、API HAR、page／console error 均無回歸。
- `frontend_check.py --compare`、`interaction_check.py --compare`（94/94）、security 16/16、185 unit／offline
  tests、`E2E_SMOKE_OK` 與 `VERIFY_OK` 全部通過；未更新 baseline。
- Classic source、minified bundle、source map 與 rollback path 保留；本次未修改 TD-03 的 Redis／worker 設定。

證據：`docs/TD02_FULL_ESM_PHASE_3-4_closure_2026-09-01.md`、`docs/TD02_FULL_ESM_build_manifest_2026-09-01.json`。

## 1.4 TD-03 本機 Redis staging probe（2026-09-01）

- 依授權啟動 workspace 隔離的 portable Redis `5.0.14.1`（`127.0.0.1:6391`），
  `save ""`／`appendonly no`，不作正式資料來源。
- real health／短 TTL sentinel、JSON-safe cache、sliding-window rate limit、owner-token
  fencing、兩個獨立 process 的 cache／single-owner consistency、disconnect timeout fault
  injection 均通過；ping p50 `0.165ms`、p95 `0.184ms`。
- 本機 Redis 5 不支援 redis-py 8 預設 RESP3 `HELLO 3`；取得授權後已將四條既有 production
  factory 明確固定 RESP2，並通過 shared-mode integration probe。此為 wire compatibility 修正，
  未改資料操作或 failure policy。
- 雙 process shared rate-limit／single-flight／cache、real disconnect fault injection 均通過；
  仍未切換 production shared modes 或 worker 數。
- 兩個獨立 `app.py` HTTP worker 也已完成 staging canary：兩邊 health 200，跨 worker 同一
  client 首次 API 200、第二次 429；每個 worker 使用 temporary SQLite／cache path。
- 本機 RDB `bgsave`、隔離 restore service 與 sentinel read-back rehearsal 通過；這不等同
  provider-native backup／restore。
- H-11-04 rollout gate 仍為 `eligible=false`；backup／restore、observation period、
  manual rollout approval 與正式 staging endpoint 仍未完成。
- 已採納替代驗證路線：新增 `regression/td03_synthetic_observation.py` 與
  `.github/workflows/td03-substitute-validation.yml`，以隔離 Redis service 重複驗證 health、
  TTL、rate-limit、lease、shared-mode 與雙 process HTTP canary；此為 CI substitute evidence，
  不代表正式 provider rollout 完成。

TD-03 最新逐項結論：client protocol compatibility、本機 Redis contract、production
shared-mode integration、雙 process／HTTP canary、fault／rollback 與本機 RDB rehearsal 已
完成；正式 provider staging、provider-native backup／restore、observation period、人工
rollout approval、production multi-worker rollout 五項正式條件均尚未完成。不可將本機替代
證據計為正式 rollout 完成。

證據：`docs/TD03_LOCAL_REDIS_STAGING_EVIDENCE_2026-09-01.md`、
`regression/td03_redis_staging_canary.py`、`regression/td03_production_shared_mode_probe.py`、
`regression/td03_http_dual_process_canary.py`、`regression/td03_synthetic_observation.py`、
`.github/workflows/td03-substitute-validation.yml`。

## 2. 三巨石行數對照

| 檔案 | 原始(稽核當時) | 現在 | 說明 |
|---|---|---|---|
| app.py | 15,514 行 | 650 行 | 拆成 13 個核心後端模組(app.py 為薄入口 + builders/cache/derivatives_store/fetch_registry/fetchers/market_config/parsers/routes_derivatives/routes_global_market/routes_system/routes_twse/security) |
| app.js | 34,150 行 | 818 行(僅剩註解/空行,無可執行程式碼) | 拆成 15 個 classic-script JS 切片(js/*.js,31,974 行) |
| styles.css | 21,973 行 | 1 行(空殼) | 拆成 7 個 CSS 切片(split-01~07.css,20,777 行) |

**用詞澄清**:app.py 的拆分是真正的 Python 模組(`import` 引用、各自獨立
命名空間)。TD-02 Phase 3～4 已讓 21 頁 production entry 進入 full-site ESM；
原 `js/*.js` classic slices、minified bundles 與 source maps 仍保留作 fallback／rollback safety net，
不代表 legacy source 已移除。895-symbol transitional bridge 仍是過渡期的可觀測契約；
後續若要移除 classic assets 或收斂 bridge，須另案提供移除證據與授權。

## 3. 護欄現況（四層核心＋TD-18／TD-19專項）

1. **安全/行為不變量**(`security_guardrail_check.py`):16 項靜態檢查,含 SQL
   參數化、escapeHtml 單一定義來源、escapeHtml 呼叫次數精確計數(現況
   1,887 次；1,905 為 TD-15 封存點)、互動基準完整性(TD-16 補的三方一致性檢查)等。
2. **API 行為基準**(`verify_against_baseline.py`):44 個端點,`--quick`
   覆蓋 40 個快取型端點(TD-17 修復:比對前先暖身快取,失敗訊息標示
   外部/程式碼),`--api-live` 覆蓋 4 個設計上永遠即時的端點
   (`live-sectors`/`live-overview`/`live-stocks`/`live-search`,
   `--full` 自動包含)。
3. **前端畫面基準**(`frontend_check.py`):21 頁截圖 pixel-diff(>2% 即
   fail)+ console 零 error。
4. **前端互動行為基準**(`interaction_check.py`,工單 00-B):21 頁、94
   步驟(P0+P1),HAR 凍結重播。
5. **TD-18 建置與 rollout 證據**：固定 lockfile／source map、21 頁效能量測、index／futures canary、minified wiring 與 classic rollback。
6. **TD-19 required-key 證據**：44/44 endpoint-policy 對帳、offline fault injection 與 failure classification。

`python -m unittest test_derivatives_platform.py regression.test_offline_verifier`:185 個 unit／offline contract tests
(原始 42 個 unit tests)。

## 4. 後續維護與暫存項目

| 項目 | 進入點 | 不做的話,實際影響 |
|---|---|---|
| TD-15 第二輪 | `docs/td15_observe_list.md`(疑似死鏈死碼群 6 符號)、`docs/td15_css_classification.md`(CSS 動態組合字首 81 個候選、grouped selector 糾纏 12 個候選) | 純維護負擔(心智負擔、易誤導未來重構者),不影響現有功能正確性——這批的三份證據標準都判定「不確定,寧可保留」,不做只是留著疑似死碼,沒有已知的使用者可感知風險 |
| TD-02 全站 ESM | `docs/TD02_FULL_ESM_PHASE_3-4_closure_2026-09-01.md` | Phase 3～4 已完成；classic source／bundle／source map 與 rollback safety net 保留，後續只處理 bridge 收斂或 legacy 移除 |
| TD-03 Redis／多 worker | `docs/TD03_LOCAL_REDIS_STAGING_EVIDENCE_2026-09-01.md`、`docs/TD03_H11_redis_rollout_deferred_2026-08-31.md` | 本機 real probe、shared-mode paths 與雙 worker probe 已完成；正式 provider staging、觀測期與 rollout 仍暫停；production 維持單 worker |
| TD-18 | 已完成本次 REMAIN-01～04；後續只在另案授權下調整 rollout 策略 | minified assets 與 route split 已導入；classic slices／source maps／rollback path 保留，後續可再評估更進階 code splitting |
| TD-19 | 已完成本次 REMAIN-01～03；後續維持政策治理 | required-key policy 已補齊 44/44；新增 endpoint 或 schema 契約變更時需同步更新 policy 與 offline fault injection |

## 5. escapeHtml 計數變動核實(2037 → 1905；現況 1887)

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

- 2026-09-01 現況基準為 `1887`；相較上述 TD-15 封存點再減少的呼叫，屬工作樹既有後續變更，已由 `verify_against_baseline.py --quick` 精確對帳，未由本次 TD-10／TD-13／TD-18／TD-19 批次改動。

## 6. 未來工單指引

若要重啟以下任一項,直接從對應的既有文件接續,不需重新從零盤點:

- **TD-15 第二輪**:讀 `docs/td15_observe_list.md` 與
  `docs/td15_css_classification.md` 剩餘候選清單,延用同一套三方證據
  標準(寧可放過,不可誤刪)。
- **TD-18**:以 `docs/TD18_前端打包效能評估_2026-08-31.md` 與既有 lockfile／manifest 接續；任何正式 asset、CSP、Service Worker 或部署策略變更須另案授權。
- **TD-19**:以 `docs/TD19_REMAIN_01-03_closure_2026-09-01.md` 與 `regression/verify_against_baseline.py` 接續；新增 endpoint 必須同步 policy、fixture 與 fault injection。
- **TD-02**:以 `docs/TD02_FULL_ESM_PHASE_3-4_closure_2026-09-01.md` 與
  `docs/TD02_FULL_ESM_build_manifest_2026-09-01.json` 接續；若要移除 classic fallback 或 transitional
  bridge，須另立小批次並完成 per-page rollback／full regression 證據。

依 CLAUDE.md 規則,重啟任一項前仍須先確認是「行為不變」或「行為變更」
型工單,後者需先提案、經使用者確認才可動工。
