# TD-02／TD-15／TD-18 後續改善規劃

日期：2026-08-31  
狀態：TD02-01、TD02-02、TD02-03 已取得授權並完成；TD15-REMAIN-01～07 已完成 review／closure；TD-18 後續批次仍未授權。

## 規劃目標與邊界

本文件承接 V2 目前尚未結案的前端相關技術債，將三項工作拆成可逐批授權、逐批驗證
的子批次。既有 classic-script slices、21 頁 HTML、global-symbol／escapeHtml 護欄與
H-10 shadow artifacts 均視為回退及比對依據。

| 技術債 | 本規劃處理 | 不在本規劃直接授權 |
|---|---|---|
| TD-02 | ES Modules／global bridge 的邊界、依賴與遷移順序設計 | 直接切換所有 HTML、移除 classic slices、改變頁面行為 |
| TD-15 | 尚存 CSS dynamic／grouped candidates 的逐項證據核實與必要的小批次刪除 | 批量刪除、不確定候選、以 baseline 更新掩蓋差異 |
| TD-18 | deterministic bundling、minify／code-splitting 可行性與 shadow／canary 門檻 | 未確認的 production asset、CSP、Service Worker、cache 或部署變更 |

TD-02 與 TD-18 有關聯但不重複：TD-02 先定義模組邊界與 global bridge 契約，TD-18 再
依該邊界驗證建置產物與效能；TD-18 不得反向迫使 TD-02 直接改變產品載入行為。

## 建議順序與子批次

一次只執行一個子批次；每批完成後先跑驗證、回寫本文件與 V2 主計畫，再等待下一批
授權。

### TD-02：前端模組邊界與遷移設計

1. `TD02-01` 依目前 21 頁 script order、895 global symbols、呼叫／初始化順序，建立
   classic slice → candidate module → required global bridge 的依賴矩陣。
2. `TD02-02` 為共用 runtime、route-specific code、頁面初始化與 legacy bridge 定義
   module boundary、命名、載入契約與回退方式；只產出設計與 verifier 方案。
3. `TD02-03` 選一個低風險、可隔離的模組做 shadow-only proof，核對 symbol、順序、
   `escapeHtml` 單一來源、初始化與錯誤行為；未經另批授權不接線正式 HTML。

TD-02 完成 gate：依賴矩陣可重現、所有跨模組 global 有理由與 owner、classic fallback
可立即恢復；不得以模組數量取代行為驗證。

### TD02-01 執行紀錄（2026-08-31）

狀態：✅完成（盤點／設計產物；未接線）

- 依現行 H-10-04 production wiring 與 `regression/td18_shadow_build.lock.json`，建立 [TD02-01 依賴矩陣](TD02-01_dependency_matrix_2026-08-31.md) 及其 [machine-readable JSON](TD02-01_dependency_matrix_2026-08-31.json)。矩陣由 `regression/td02_01_dependency_matrix.py` 產生，可用 `--check` 重現比對。
- 證據範圍：21 頁、895/895 global symbols、18 個 classic fallback input、69 條跨 slice dependency edges、468 個跨 slice references；每個 symbol 均記錄唯一 owner、candidate module 與 consumers。
- 已記錄 `main ↔ page-tw` 及 futures/options/assethub 三方循環、4 組頂層立即執行引用，以及 `TWSE_DATA`／`TWSE_ALL_STOCKS`、`currentGlobalMarketPayload`、innerHTML safety sentinel 等 dynamic window 契約，交由 TD02-02 定義正式 import／bridge 命名。
- 本批只新增盤點器與文件；未切換 HTML、未移除 classic slices、未修改 baseline、CSP、headers、Service Worker、cache、部署設定、SQLite 或 `twse-cache.json`。classic fallback 與 H-10 bundle 產物均保留。
- 驗證：`python -m py_compile app.py regression/td02_01_dependency_matrix.py` 通過；矩陣 `--check` 通過；既有 unit 176 tests 通過；security 16/16 通過；根目錄 `python e2e_smoke.py` 輸出 `E2E_SMOKE_OK`；允許外部連線重跑 `python regression/verify_against_baseline.py --full` 輸出 `VERIFY_OK`（21/21 frontend、94/94 interaction）。受限環境首次 full verify 的 TWSE 502／瀏覽器 `ERR_NETWORK_ACCESS_DENIED` 已分類為 `[外部問題]`，未更新 baseline。
- 回退：移除本批矩陣文件／盤點器即可；若後續接線，仍以 lockfile 的 classic input order 恢復 HTML 入口。

TD02-01 已完成盤點 gate；TD02-02 已完成設計 gate。TD02-03 已另批授權並完成 shadow-only proof。

### TD02-02 執行紀錄（2026-08-31）

狀態：✅完成（模組邊界／載入契約／verifier 設計；未接線）

- 產出 [TD02-02 模組邊界設計](TD02-02_module_boundary_design_2026-08-31.md)，定義 `runtime/*`、`route/*`、`compat/*` candidate naming、source／semantic owner 原則與 named import／explicit bridge／deferred callback 三類跨模組邊。
- `main ↔ page-tw` 採預留 `runtime/live-data` loader contract 解循環；futures/options/assethub 第一階段合併為 `route/global-market` module island，避免以重排 script 或重複 helper 掩蓋循環。
- 定義 `compat/legacy-global-bridge` 的 named-symbol、mutable-state、entrypoint、window-property 四類契約，並列出 895 symbol owner、top-level initialization、dynamic window、CSP、escapeHtml、DOM/pixel/interaction、rollback 與錯誤注入 verifier gate。
- 本批只新增設計文件；未建立 ESM 檔案、未修改 HTML／classic slices／baseline／CSP／headers／Service Worker／cache／部署設定／SQLite／`twse-cache.json`。
- 驗證：TD02-01 matrix `--check` 通過；本批 `py_compile`、既有 unit 176 tests、security 16/16、根目錄 `e2e_smoke.py` 的 `E2E_SMOKE_OK` 均通過；允許外部連線重跑 `python regression/verify_against_baseline.py --full` 輸出 `VERIFY_OK`（21/21 frontend、94/94 interaction）。本批無 runtime source 變更，另完成文件 diff／命名與排除範圍檢查。正式 ESM shadow verifier 的實作與 TD02-03 proof 仍待另批授權。
- 回退：移除本設計文件即可；後續若接線，依 TD02-01 lockfile 的 classic input order 回復 HTML entry。

TD02-02 完成後進入 TD02-03 shadow-only proof；正式 ESM／HTML 接線仍需另批授權。

### TD-02 全站 ESM 遷移 roadmap（暫時封存；全站尚未完成）

TD02-REMAIN-01～03 已完成 bridge、單頁 ESM island、classic fallback 與 canary proof；這只代表
單頁遷移路徑已驗證，並不代表全站 ESM 已完成。目前 `derivatives-status.html` 是 ESM island，
其餘頁面仍依 classic-script slices 與既有 script order 運作。

後續全站遷移分為以下獨立 gate，每次只處理一個 page／route wave，完成驗證後再取得下一批授權：

1. **Readiness／分波**：重跑 895/895 global-symbol matrix，依 shared runtime、route code、
   initializer、DOM／window state 與循環依賴分組；凍結 wave 範圍與 owner，保留 classic fallback。
2. **Contract／bridge**：把跨 slice global 收斂為 named import、explicit bridge 或 deferred
   callback；為 mutable state、API error、`escapeHtml`、listener、polling 與 initialization
   side effect 定義 owner、生命週期與 duplicate-run guard。
3. **Wave migration／canary**：先 shadow 驗證，再由 feature flag／loader 接線；正常模式使用
   ESM，legacy browser、load error 或 rollback 立即恢復原 classic asset 與 script order。
4. **Site closure／legacy removal**：21 頁均完成 ESM wiring、正常／rollback canary，並通過
   symbol、DOM／API、CSP、security、interaction、E2E 與 full verify 後，才另案提出移除 classic
   slices。未達成前，classic assets、loader fallback 與 rollback path 不得移除。

全站完成判定：21/21 page wiring、895/895 symbol／bridge、94/94 interactions、API success／
timeout／error、DOM／pixel、security／CSP、`escapeHtml` single-source、E2E、full verify 及
每個 wave 的 rollback rehearsal 全部通過。外部 API／瀏覽器網路阻擋須標記為外部問題，不能以
更新 baseline 取代修正。

回退：停用該 wave 的 ESM flag／loader → 恢復原 classic asset／script order → 保留 ESM artifact
供修正。

本次授權執行結果（2026-09-01）：已完成 21 頁／895 symbols 的 freeze 與 6-wave manifest，並將
TD02-02 bridge 設計鎖定為 477 筆 machine-readable entries；production wiring、HTML、baseline、
classic fallback 均未變更。因目前 browser backend 不可用，Phase 3 逐波接線與 Phase 4 全站收斂
停在 browser-backed shadow gate 前；依最新決定，TD-02 全站 ESM 後續暫時封存，不能宣稱全站 ESM 已完成。證據見
[`TD02 full ESM freeze`](TD02_REMAIN_full_esm_freeze_2026-09-01.md) 與
[`TD02 full ESM bridge contract`](TD02_REMAIN_full_esm_bridge_contract_2026-09-01.md)。

### TD02-03 執行紀錄（2026-08-31）

狀態：✅完成（`runtime/api` shadow-only proof；未接線）

- 依 TD02-02 選定低風險 `js/api.js`／`runtime/api` candidate。該 slice 只有 `fetchWithTimeout` 一個頂層 symbol，無頂層立即引用、DOM／window 依賴，且 TD02-01 matrix 無 incoming/outgoing dependency edge，classic order 為 `core → api → shared-calc`。
- 新增可重跑的 `regression/td02_03_api_shadow.py` 與 [TD02-03 shadow proof report](TD02-03_api_shadow_proof_2026-08-31.md)。verifier 只在系統 temp 目錄生成一次性 ESM wrapper／Node harness，不修改 `js/api.js` 或任何正式 asset。
- Symbol／order／初始化／錯誤 gate 全部通過：ESM 僅 export `fetchWithTimeout`；import fetch side effect `0`；success 保留 response／options／AbortController signal；upstream rejection 保留；timeout 產生 `AbortError`。
- `escapeHtml` 全站 `app.js + js/*.js` 僅 1 份 definition，owner 為 `js/core.js`。source fingerprint：`js/api.js` SHA-256 `9a633652fedd9d98d939a97a0ef42fb133a482f899a622c1a3f652a7c9eb20be`。
- 本批未建立正式 ESM、未修改 HTML／classic slices／bundle／source map／baseline／CSP／headers／Service Worker／cache／部署設定／SQLite／`twse-cache.json`。正式 ESM 或 HTML wiring 不因本 proof 自動獲得授權。
- 驗證：`py_compile`、TD02-01 matrix `--check`、TD02-03 shadow verifier、既有 unit 176 tests、security 16/16、根目錄 `e2e_smoke.py` 的 `E2E_SMOKE_OK` 均通過；允許外部連線重跑 `python regression/verify_against_baseline.py --full` 輸出 `VERIFY_OK`，包含 21/21 frontend、94/94 interaction 與 security；未更新 baseline。
- 回退：移除本批 shadow verifier／proof report 即可；現行 classic source、lockfile 與 production wiring 保持 authoritative。

### TD-15：CSS 候選重新核實與逐組清理

1. `TD15-01` 更新 dynamic candidates 的 JS／HTML 產生路徑與 21 頁／94 條互動對帳；
   證據不足者明確保留。
2. `TD15-02` 逐組核對 grouped selectors 的 shared branch、responsive、active／focus／
   hover 與 cascade；每批最多處理一個明確候選組。
3. `TD15-03` 僅對 AST／HTML-JS／runtime 或頁面三方證據一致的候選執行精確刪除，
   立即做 CSS 命中重掃、21 頁 frontend、94 條 interaction、security 與 full verify。

TD-15 完成 gate：每個刪除組都有可回復 diff 與三方證據；不確定項目保留，不修改
baseline 來消除 pixel diff。

### TD-18：Bundling／minify／code-splitting 評估與受控 rollout

1. `TD18-01` 盤點並固定 Node／bundler／lockfile、輸入清單、輸出命名、source map、
   minify／code-splitting 方案與 artifact hash；沿用 H-10 deterministic shadow build
   證據，不覆寫現行 assets。
2. `TD18-02` 在隔離目錄比較未壓縮、minify、route split 的 bytes、request count、
   cold／warm latency、source map 與 error stack 可追溯性，建立成本／收益／風險矩陣。
3. `TD18-03` 以代表性低風險頁面執行 shadow／canary，必須保持 895/895 global symbols、
   `escapeHtml` 單一來源、script order、CSP、local asset 404=0、DOM／pixel／interaction
   與效能門檻。
4. `TD18-04` 產出全頁 rollout 方案、觀測指標與 classic-slice rollback 操作；只有另
   取得明確變更授權後，才可執行 HTML／assets／CSP／Service Worker／cache／部署接線。

TD-18 完成 gate：shadow artifact deterministic；canary 無未分類回歸；classic slices
仍可立即回退；正式接線與部署變更不因本規劃而自動獲得授權。

## 共用驗證與回退

每一個獲授權子批次均須依受影響檔案執行語法檢查、unit tests、security 16/16、
`E2E_SMOKE_OK`，以及 `python regression/verify_against_baseline.py --full`。前端批次
另須依適用範圍核對 21 頁 frontend、94 條 interaction、global-symbol 與 CSP；外部
服務錯誤標記 `[外部問題]`，不得更新 baseline 消除差異。

- TD-02：回退該批 module／bridge diff，恢復原 classic script order。
- TD-15：以該批精確 diff 還原被刪 CSS rule blocks，不回退其他候選。
- TD-18：HTML 入口切回 classic slices，保留 shadow artifacts 與 failure evidence；
  CSP、`CACHE_VERSION`、Service Worker、部署設定與正式 assets 均須另批授權。

## 明確排除

TD-03 整體目前為部分完成、暫時封存；不處理 H-11 Redis 實連／多 worker rollout。封存總結見
`docs/TD03_archive_2026-09-01.md`，細項 deferred record 見
`docs/TD03_H11_redis_rollout_deferred_2026-08-31.md`。本規劃也不修改正式 SQLite、
`twse-cache.json`、baseline、CSP、headers、Service Worker、`Procfile` 或 `render.yaml`。

## TD15-REMAIN final update（2026-09-01）

TD15-REMAIN-01～07 已完成。263 個 CSS rule blocks 均已完成 current identity、evidence 與 disposition；最終 `retain=263`、`observe=0`、`delete_candidate=0`、`blocked=0`。REMAIN-07 因沒有安全刪除候選而採 no-op closure，未修改 CSS／baseline／runtime data。詳見 `docs/TD15_REMAIN_07_evidence_2026-09-01.md`。

## 既有依據

- `docs/工單TD02_前端拆分.md`
- `docs/工單TD15_前端死碼清理.md`
- `docs/TD18_前端打包效能評估_2026-08-31.md`
- `docs/td15_css_classification.md`
- V2 主計畫 H-10 shadow／canary 執行紀錄
