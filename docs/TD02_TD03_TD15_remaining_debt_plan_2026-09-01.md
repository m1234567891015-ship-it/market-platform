# TD-02／TD-03／TD-15 剩餘技術債後續處理規劃

日期：2026-09-01  
文件狀態：TD-02 全站 ESM Phase 3～4、TD02-REMAIN-01～03、TD15-REMAIN-01～07、TD-10、TD-13、TD-18、TD-19 已完成驗證與 closure；TD-03 本機替代驗證已完成，但正式 Redis staging／多 worker rollout 仍暫時封存  
適用專案：Market Pulse V1.0 R6

## 1. 目的與結論

本文件獨立盤點 TD-02、TD-03、TD-10、TD-13、TD-15、TD-18、TD-19 在既有批次完成後仍可由證據明確界定的剩餘技術債，並規劃後續逐批處理順序、依賴、驗收 gate 與 rollback 路徑。

目前結論如下：

| 技術債 | 目前狀態 | 明確剩餘項目 | 後續原則 |
|---|---|---|---|
| TD-02 前端模組邊界 | ✅ Phase 3～4 closure | 21 頁 full-site ESM 已接線；895-symbol transitional bridge、classic fallback 與 rollback 保留 | 維持 per-page rollback；若要移除 classic source 或收斂 bridge，另開小批次 |
| TD-03 跨 worker 狀態 | 🟡 部分完成／暫時封存 | 本機 Redis real probe 與雙 process contract 已通過；production shared-mode 相容性、正式 staging／雙 worker rollout 尚未完成 | 封存期間維持 local／單 worker；解封須重新授權並具備支援 RESP3 的實連 staging、backup／restore、觀測期與 rollout 核准 |
| TD-10 測試覆蓋 | ✅ REMAIN-01～03 已完成 closure | 10/10 top-10 builder／fetcher 已有離線 fixture、contract test 與適用錯誤／空資料分支 | 維持 matrix；函式或回應契約變更時增補同批測試 |
| TD-13 Python 例外處理與行尾 | ✅ REMAIN-01～03 已完成 closure | 161 個 production broad exception 均完成分類；131 direct log、25 delegated API log、5 translate/re-raise、0 未決靜默 | 維持最低限度安全 logging；不得記錄敏感 query／外部完整回應 |
| TD-15 CSS 候選清理 | ✅ REMAIN-01～07 已完成 closure | 263 個 rule blocks 已完成逐項 evidence review；65 個 grouped／compound、198 個 dynamic／status／direct-reference；最終 retain=263、delete candidate=0、blocked=0 | 維持保守保留；若未來 source／頁面行為改變，須重建 identity 與 evidence 後另開 ≤20 blocks 批次 |
| TD-18 前端建置與資產效能 | ✅ REMAIN-01～04 已完成 closure | deterministic shadow／minify、21 頁效能量測、index／futures canary、正式 minified wiring 與 rollback package 均完成 | classic slices、source maps 與 rollback path 保留；後續只在另案授權下變更部署策略 |
| TD-19 schema required-key 護欄 | ✅ REMAIN-01～03 已完成 closure | 44/44 manifest endpoint 與 policy 一對一；required-key removal、null／empty、error-only 與 failure label 均有 offline fault injection | 維持非關鍵時變 key 的 structure-only 容忍，不把所有 key 硬編成 required |

TD-18 的 deterministic shadow／minify toolchain、lockfile、效能量測、canary 與 production wiring 已完成本次授權範圍；classic fallback、source map 與回退路徑仍保留。

## 2. 已完成項目與本次不重複範圍

以下項目已由既有文件與驗證記錄覆蓋，不再重開同名批次：

- TD-02：classic-script 切片、載入順序、模組邊界盤點、full-site ESM loader、895-symbol bridge、21 頁 wiring 與 rollback 已完成；classic source 作為安全網保留。
- TD-03：single-worker contract、process-local 警示、限制與測試已完成；H-11 Redis 設計／延後決策已記錄，但真實 Redis staging rollout 未完成。
- TD-10：`TD10_REMAIN_01-03_evidence_2026-09-01.md` 已固定 top-10 matrix、離線 fixture、contract tests 與 coverage closure。
- TD-13：`TD13_REMAIN_01-03_evidence_2026-09-01.md` 與 `regression/td13_exception_inventory.py` 已完成 broad exception inventory、最低限度 logging 與敏感 query fault injection。
- TD-15：R0 manifest／證據重建、R1 candidate-only CSS 清理、R2 unloaded legacy grouped CSS 清理、R3 JS audit、REMAIN-01～07 全部完成；目前沒有可直接宣稱刪除的全域候選。
- TD-18：`TD18_前端打包效能評估_2026-08-31.md` 已補齊 REMAIN-01～04 結果；正式 minified assets、版本化 immutable cache、Service Worker version 與 21 頁 HTML wiring 已完成，classic fallback 保留。
- TD-19：`TD19_REMAIN_01-03_closure_2026-09-01.md` 已完成 44/44 policy 對帳、required-key fault injection 與 offline verifier closure。

## 3. 剩餘項目定義

### 3.1 TD-02：正式模組化遷移

目前 production entry 已由 `market-pulse-esm-loader.js` 導入 full-site ESM；原 classic slices、minified bundles 與 source maps 仍保留為 fallback／rollback safety net。895-symbol transitional bridge 讓既有 owner 對帳與 legacy consumer 在遷移期間可觀測。

目前完成項目：

1. 既有全域依賴已由 full-site ESM module 與 transitional bridge 接管。
2. 21 頁已完成 ESM entry wiring，並以固定 HAR／browser runner 完成 normal／rollback canary。
3. 初始化、事件 listener、polling、API fallback 與錯誤處理已通過 21 頁與 94 steps regression。
4. Classic fallback、source map、loader rollback 與 Service Worker/cache version 均保留。

#### 3.1.1 全站 ESM 遷移後續規劃與完成定義

TD02-REMAIN-01～03 已證明 bridge、單頁 island、ESM／classic rollback 與 canary 路徑可行；本次
Phase 3～4 已將同一可回退 loader 接到 21 頁，並完成 full-site ESM bundle 與 browser gate。

全站遷移採逐頁、可回退、每批獨立授權的路線：

1. **遷移前凍結與分波**：重跑 895/895 global-symbol dependency matrix，依 shared runtime、
   route-specific code、page initializer、DOM／window state 與循環依賴分組；每一波只選一個低風險
   page／route island，保留 classic fallback，不以檔案搬移數量作為完成判定。
2. **bridge contract 落地**：將跨 slice global 改為 named import、explicit bridge 或明確的
   deferred callback；所有 mutable state、API error、`escapeHtml`、事件 listener、polling 與
   initialization side effect 都要有 owner、生命週期與重複執行防護。
3. **逐波 ESM 接線**：每個 page／route wave 先在 shadow harness 驗證，再以可觀測 feature flag／
   loader 接線；正常模式走 ESM，legacy browser、module load error 或人工 rollback 立即回到既有
   classic bundle／script order。未通過該波 gate 不得擴大下一波。
4. **全站收斂與移除條件**：21 頁均完成 ESM wiring、至少一次正常與 rollback canary，且確認沒有
   duplicate listener／polling、global symbol 漂移、DOM／API／CSP／XSS regression 後，才可另案
   提出移除 classic slices；在此之前 classic assets、loader fallback、lockfile 與 rollback path
   均視為 production safety net。

全站 ESM 驗收 gate：21/21 頁載入契約、895/895 symbol／bridge 對帳、94/94 interactions、API
success／timeout／error、DOM／pixel、security／CSP、`escapeHtml` single-source、E2E 與 full
verify 均通過；另須完成至少一次 per-wave rollback rehearsal。任何外部 API 或瀏覽器網路阻擋須
標記為外部問題，不得更新 baseline 掩蓋差異。

回退路徑：逐頁停用 ESM flag／loader → 恢復該頁原 classic asset 與既有 script order → 保留
ESM artifact 供修正；只有在全站遷移完成且另取得刪除授權後，才可移除 legacy source／bundle。

#### 3.1.2 本次授權執行與 closure 狀態（2026-09-01）

已完成遷移前凍結與分波，以及 bridge contract lock：21 頁／895 symbols 已重新對帳，分為 6 波；
已鎖定 477 筆 machine-readable bridge entries（468 required global bridge、5 entrypoint、
4 window property），並完成 owner drift error injection。詳見
[`TD02 full ESM freeze`](TD02_REMAIN_full_esm_freeze_2026-09-01.md) 與
[`TD02 full ESM bridge contract`](TD02_REMAIN_full_esm_bridge_contract_2026-09-01.md)。

本次已取得 Phase 3～4 明確授權，完成 21 頁 HTML 接線、full ESM bundle、loader fallback、browser-backed
shadow、normal／rollback canary 與正式 asset whitelist／cache wiring。21/21 page wiring、895/895
symbol bridge、94/94 interactions、API／DOM／pixel／security／E2E／full verify 全部通過，baseline 未更新。
完整證據見 [`TD02 full ESM Phase 3-4 closure`](TD02_FULL_ESM_PHASE_3-4_closure_2026-09-01.md)。

### 3.2 TD-03：跨 worker 狀態外部化（暫時封存）

目前安全運行契約仍是 `app:app`、單 worker。依最新決定，TD-03 production rollout 仍暫時封存；本次授權已在 workspace 啟動隔離 Redis 並完成 real adapter／雙 process probe，但這不等同正式 staging 或 rollout。封存期間不切換 shared mode、不增加 worker、不修改部署設定。

#### 3.2.1 本機 Redis staging probe（2026-09-01）

`regression/td03_redis_staging_canary.py` 以隨機 staging namespace 完成 PING／TTL、JSON-safe
cache、sliding-window rate limit、owner-token fencing、兩個獨立 process 的跨 worker consistency
與 disconnect timeout fault injection；結果為 `TD03_REDIS_STAGING_CANARY_OK`。完整數據見
[`TD-03 local Redis staging evidence`](TD03_LOCAL_REDIS_STAGING_EVIDENCE_2026-09-01.md)。

本機可攜 Redis 為 `5.0.14.1`，probe 明確使用 RESP2；本次授權已將四條 production factory
明確固定 RESP2，並以真實 service 完成 shared-mode integration probe、雙 process probe 與
本機 RDB backup／restore rehearsal。仍須提供正式 provider staging，完成 provider-native
backup／restore、觀測期與人工 rollout approval。

剩餘債務：

1. （解封後）取得 staging Redis 連線、provider／region／成本、namespace、backup／restore owner 與觀測窗口；在此之前以 CI 隔離 Redis service 跑 substitute validation。
2. 驗證 PING、TTL、L2 JSON-safe bucket、timeout、斷線 fallback、fail-closed 邊界。
3. 在雙 worker staging 驗證 rate limit 一致性、single-flight、lease takeover 與 fencing，並量測 p50／p95／p99。
4. 完成人工放行與可回退的 rollout；在此之前不得將 production worker 數或部署設定改為共享狀態模式。

替代驗證已納入 `regression/td03_synthetic_observation.py` 與
`.github/workflows/td03-substitute-validation.yml`，可在沒有正式 provider secret 的情況下
重複執行 bounded synthetic observation、shared-mode integration 與雙 process HTTP canary。
此路線降低回歸風險，但不將 TD-03 標記為正式完成；production 仍維持 single worker／local
shared modes，正式 provider、backup／restore、觀測期、人工核准與 multi-worker rollout
五項條件仍須另案完成。

### 3.3 TD-10：高風險後端函式特性測試補強

TD-10 的問題不是單純測試數量不足，而是重構後關鍵 builder／fetcher 的輸入邊界、空資料、
外部失敗與回應契約沒有一份可重跑的特性測試清單。既有 unit／regression tests 與 offline
fixture 是輸入，不把目前測試總數直接視為 TD-10 closure。

剩餘債務：

1. 以函式規模、外部依賴、共享狀態、歷史缺陷與 21 頁使用範圍建立 top-10 高風險函式清單，
   並逐一對帳現有測試；清單需固定 owner、輸入 fixture、輸出 schema 與錯誤契約。
2. 為每個入選函式建立 deterministic、離線、可重跑的 fixture／golden 或等價 contract test；
   fetcher 不得在測試中依賴即時 TWSE／TAIFEX／Yahoo。
3. 依適用性覆蓋正常、空資料、格式異常、timeout／上游錯誤與 fallback 分支；不得為了通過
   測試放寬既有 schema、錯誤信封或安全邊界。
4. 以完整 regression 與既有基準確認新增測試沒有改變 production 行為；未涵蓋的函式與理由
   必須留在 manifest，不以「已有相近測試」代替逐項判定。

TD-10 完成 gate：top-10 清單 10/10 有明確測試對應；每項至少有一個正常契約與適用的錯誤／
空資料分支；fixture 可離線重跑；unit、security、E2E、quick baseline 全部通過。rollback
為移除本批新增測試／fixture／manifest，不回退 production source。

### 3.4 TD-13：例外處理可觀測性與行尾收斂

`.gitattributes` 已完成 LF 正規化，但 broad `except Exception` 中仍可能有少數靜默吞錯路徑。
本批只處理證據確認的靜默例外，不以全域搜尋結果直接推導修改，也不把預期 fallback 誤改成會
暴露內部細節的錯誤。

剩餘債務：

1. 盤點 production Python 模組中的 broad exception，分類為：已有 log、預期 fallback、刻意
   忽略且有註解、真正靜默且缺少診斷資訊；排除測試工具與已知外部錯誤攔截器後固定清單。
2. 只對真正靜默的路徑補最低限度 `LOGGER.debug`／適當級別記錄，內容不得含 token、cookie、
   個資、完整外部回應或敏感 query；保留原有回傳值、fallback 與 HTTP 行為。
3. 為修改過的例外路徑補 fault-injection／response contract test，證明 log 增加不會造成
   exception re-raise、錯誤信封改變或 rate-limit／cache 行為改變。
4. 對受影響檔案執行行尾、語法、security 與完整回歸檢查；不做無關的整檔格式化。

TD-13 完成 gate：所有列入清單的靜默路徑均有決策（補 log、保留並說明或另立工單）；行尾
檢查為 LF；安全檢查、unit、E2E 與 baseline 全部通過。rollback 為逐 hunk 還原 logging
變更，不撤銷 `.gitattributes`。

### 3.5 TD-18：建置產物、效能證據與受控 rollout

目前已有 H-10 deterministic shadow／minify 建置基礎、Node／Terser 設定與部分 bundle 產物，
但 artifact 可重現不等於效能已證明，也不等於 21 個 HTML 入口已完成受控切換。TD-18 只在
取得各批明確授權後改動正式 HTML／資產／CSP／Service Worker／cache 或部署設定。

剩餘債務：

1. `TD18-REMAIN-01` 固定 Node／bundler／lockfile、輸入清單、輸出命名、source map、artifact
   hash 與建置環境；隔離輸出，不覆寫正式資產，並證明相同輸入可產生相同輸出。
2. `TD18-REMAIN-02` 建立未壓縮、minify、route split 的 bytes、request count、cold／warm
   latency、source map 與 error stack 可追溯性比較；需要 browser backend 的數據不得以本機
   模擬或估算冒充實測，環境不可用時標記 blocked。
3. `TD18-REMAIN-03` 選低風險入口做 shadow／canary，驗證 global symbols、script order、
   `escapeHtml` 單一來源、CSP、local asset 404、DOM／pixel／interaction 與錯誤回退；正常
   與失敗路徑均需能回到既有 classic assets。
4. `TD18-REMAIN-04` 產出 21 頁 rollout／觀測／rollback package；只有另取得明確變更授權，
   才能執行正式 HTML／assets／CSP／Service Worker／cache／部署接線。

TD-18 完成 gate：shadow artifact deterministic、效能數據可重現、canary 無未分類回歸、
classic fallback 可立即恢復；正式接線仍須另有變更核准。rollback 順序固定為入口切回 classic
assets → 還原原 script order → 保留 shadow artifacts 與 failure evidence。

### 3.6 TD-19：schema required-key 契約護欄

目前 `regression/verify_against_baseline.py` 已有 `REQUIRED_KEY_PATHS`、error-only endpoint
分類與 offline fixture 分流；剩餘風險是 required-key policy 本身若漏列、錯列或沒有故障注入，
仍可能形成護欄盲區。一般 `structure_only` 對時變欄位的新增／刪除容忍規則不在本批全面移除。

剩餘債務：

1. `TD19-REMAIN-01` 逐一盤點 baseline manifest 的每個 endpoint，建立 required path、可為
   null／空值的語意、error-only policy 與 owner；驗證 policy 與 manifest 一對一，不接受漏列
   或多餘列。
2. `TD19-REMAIN-02` 以離線 fixture 做 fault injection：移除 required key 必須 FAIL，key 存在
   但值為 null／空集合依契約判定，新增非關鍵 key 維持既有容忍，error-only endpoint 不得被
   誤判為 healthy success。
3. 將上述案例納入 regression tests，並保留可讀的 failure label，區分 verifier 設定缺漏、
   程式碼回應格式回歸與外部資料源失敗。
4. `TD19-REMAIN-03` 完成全 manifest 對帳與 closure report；不得更新 baseline 來掩蓋缺欄位
   failure，也不得把所有 schema key 都硬編成 required 以消除時變資料差異。

TD-19 完成 gate：manifest endpoint 與 policy 100% 一對一；required-key removal fault
   injection 會 FAIL；offline quick、unit、security、E2E 與適用的 full verify 通過。rollback
   為還原本批 policy／fixture／test diff，保留原有 `schema_diff` 的明確容忍範圍。

### 3.7 本次授權執行 closure（2026-09-01）

| 批次 | 結果 | 主要證據 |
|---|---|---|
| TD10-REMAIN-01～03 | ✅ closed | 10/10 matrix、離線 fixture／contract tests；185 tests 通過 |
| TD13-REMAIN-01～03 | ✅ closed | 161 broad exception inventory：131 direct log、25 delegated API log、5 translate/re-raise、0 未決靜默；query value omission test 通過 |
| TD18-REMAIN-01～04 | ✅ closed | minify verifier、21 頁 measurement、index／futures canary、production wiring／rollback verifier 通過；895/895 symbols、21/21 pages |
| TD19-REMAIN-01～03 | ✅ closed | 44/44 endpoint-policy 對帳、8 個 offline fault-injection tests、quick/full verify 通過 |

共同驗證結果：`security_guardrail_check.py` 16/16、`E2E_SMOKE_OK`、`VERIFY_OK`（API quick/live、21 頁 frontend、94/94 interactions）。完整證據見 `docs/TD10_REMAIN_01-03_evidence_2026-09-01.md`、`docs/TD13_REMAIN_01-03_evidence_2026-09-01.md`、`docs/TD18_前端打包效能評估_2026-08-31.md` 與 `docs/TD19_REMAIN_01-03_closure_2026-09-01.md`。

本次 full／canary 使用外部連線重跑；受限環境下曾出現 `WinError 10013`／`ERR_NETWORK_ACCESS_DENIED`，未更新 baseline，外部連線可用後已全綠。

### 3.8 TD-15：CSS 候選重新核實與後續清理

既有 R0～R3 已完成一次證據化處理。後續範圍是現況 manifest 中的全部 263 個 rule
blocks，不只處理 candidate-only。現況應視為「保留為主」：production split CSS 中仍有
grouped／compound／responsive／state 規則，以及 dynamic／status／direct-reference 規則；
這些不能僅因靜態命中或歷史名稱而刪除。

目前 closure：

1. REMAIN-04～07 已完成 263 個 current rule blocks 的逐項 evidence、disposition 與最終對帳。
2. REMAIN-05 的 65 個 grouped blocks 與 REMAIN-06 的 198 個 dynamic blocks 全部 `retain`；沒有 `delete_candidate` 或 `blocked`。
3. REMAIN-07 已完成 no-op closure；未執行 CSS 刪除、未修改 baseline／runtime data，CSS source hashes 維持一致。

後續維護原則：

1. 若 CSS／HTML／JS 或頁面行為變更，重建 current manifest，記錄 selector、檔案、行號／hash、引用、runtime 與畫面／互動覆蓋。
2. 只有同時具備完整三層證據的少量 candidate-only 規則，才可形成下一批；每批上限 20 個 blocks。
3. 每一批均需驗證 21 頁、94 條互動路徑與 CSS／DOM／pixel 影響；若證據不足，保留並記錄原因。
4. JS 只有在出現新的完整三層證據時才可另立候選；不得以 R3 的零命中結論推導刪除。

### 3.9 TD-15 現況剩餘技術債清單（2026-09-01）

以下清單以 [TD15-REMAIN-01 逐 rule-block manifest](TD15_REMAIN_01_css_rebaseline_2026-09-01.json)
與 [TD15 R0 inventory](TD15_residual_inventory_2026-09-01.md) 為現況來源。數量是目前
仍存在的 rule blocks／候選範圍，不是可直接刪除的清單。

| ID | 剩餘技術債 | 現況證據與範圍 | 目前決定 | 後續處理 |
|---|---|---|---|---|
| TD15-CSS-GROUPED-01 | production split CSS 的 grouped／compound rule blocks | 65 blocks；REMAIN-05 已完成 branch／cascade／responsive／state／reference review | `retain`（closed） | 若未來 source／行為改變才重開 ≤20 blocks review；不得沿用舊行號 |
| TD15-CSS-DYNAMIC-01 | dynamic／status／direct-reference CSS 的使用路徑 | 198 blocks、129 個目前出現的 candidate names；REMAIN-06 已完成 generator／狀態／runtime coverage | `retain`（closed） | 若未來出現新證據才重開 ≤20 blocks review；不得以 default screenshot 零命中刪除 |
| TD15-CSS-RESPONSIVE-STATE-01 | responsive、hover／focus、active／disabled、漲跌／警示／stale 等非預設狀態 | 已納入 REMAIN-05／06 review；不足證據的 branch 全部保留 | `retain`（closed） | 前端行為變更後重建 evidence；不得因 default screenshot 零命中刪除 |
| TD15-CSS-EVIDENCE-01 | 下一個安全刪除 queue | REMAIN-07 closure：263 blocks、`candidate-only-review=0`、delete candidate=0、blocked=0 | `closed；不開 deletion batch` | 未來只有新且完整三層證據才開 ≤20 blocks 批次 |
| TD15-JS-AUDIT-01 | JS 死碼清理目前無可刪 residual，但需維持稽核閉環 | R3：58 個歷史符號目前 declaration、literal hit、candidate dynamic hit 均為 0 | `closed-for-now`；不刪 | 前端 source 或入口變更後重跑 R3；若重新出現可疑符號，另開 ≤20 symbols 的獨立證據批次 |
| TD15-CSS-SCOPE-ALL-263 | 263 個現況 CSS rule blocks 的最終 closure | REMAIN-04～07 已逐項完成 current file、行號、selector、hash、三層 evidence 與 disposition | `closed` | 若未來內容變更，重新以 manifest 為唯一清單並另開 ≤20 blocks 批次 |

### 3.10 TD-15 全量處理的完成定義

「全部 263 個 blocks 要處理」的定義是：263 個 blocks 全部完成逐項證據審查與 disposition，
不是預先承諾 263 個 blocks 全部刪除。每個 block 必須以 current file／startLine／endLine／
selector／SHA-256 對應 manifest，並且只能落入下列其中一種結果：

1. `delete`：CSS、HTML／JS／Python literal、runtime／DOM、responsive／state／cascade
   三層證據完整，且該 ≤20 blocks 批次通過明確授權與完整回歸。
2. `retain`：仍有 grouped／compound、live branch、responsive、state、status 或 direct
   reference，證據支持保留。
3. `observe`：可疑但 generator、dynamic access 或非預設狀態尚未收斂；證據不足即保留觀察。
4. `blocked`：manifest、source、baseline owner 或 runtime 條件不一致；先記錄阻塞，不刪除。

目前 65 個 grouped／compound 與 198 個 dynamic／status／direct-reference 均已完成全量
review；`candidate-only-review=0` 且 REMAIN-07 已確認 delete candidate=0，因此本輪沒有 deletion
batch。這代表 review／closure 已完成，不代表所有保留 CSS 都被刪除。

### 3.11 TD-15 剩餘債務的執行規畫

TD15-REMAIN-01～03 已完成：已重建現況 manifest、完成三層 evidence rebaseline、確認
沒有 candidate-only deletion candidate，並以保留／結案方式封存目前批次。接續工作改為
完整覆蓋 263 個 blocks 的逐項審查；每個 review packet 最多 20 個 blocks，後續不是預設
刪除，而是依每個 block 的新證據決定 disposition：

| 順序 | 批次 | 執行內容 | 進入條件 | 完成判定 |
|---:|---|---|---|---|
| 1 | TD15-REMAIN-04 | 263 blocks 全量 review manifest 分包與逐項 disposition | current manifest 穩定；依 65 grouped／compound、198 dynamic／status／direct-reference 分包，每包 ≤20 blocks | 263 個 blocks 均有 exact identity、證據狀態、責任人／決策與原因；不得以 summary 代替逐項記錄 |
| 2 | TD15-REMAIN-05 | 65 個 grouped／compound／responsive／state blocks review | REMAIN-04 分包完成；每包最多 20 blocks | 每個 block 完成 cascade、live branch、responsive、state、HTML／JS／runtime review；結果為 retain／observe／delete candidate／blocked |
| 3 | TD15-REMAIN-06 | 198 個 dynamic／status／direct-reference blocks coverage review | REMAIN-04 分包完成；能追蹤 generator、資料欄位、`classList`／template 與狀態集合 | 每個 block 完成 generator／狀態／runtime evidence；結果為 retain／observe／delete candidate／blocked |
| 4 | TD15-REMAIN-07 | 對所有 `delete candidate` 執行小批刪除與最終閉環 | REMAIN-05／06 產生完整三層證據，且取得每一批明確授權；每批 ≤20 blocks | reverse diff 可回復；21 頁、94 steps、security、E2E、full verify 全綠；其餘 blocks 均有 retain／observe／blocked 原因 |

目前執行決策：REMAIN-04～07 已完成授權執行與驗證。REMAIN-07 確認沒有 delete candidate，
因此採 no-op closure；所有 263 個 blocks 均已以 `retain` 記錄。若未來出現可刪候選，必須由
current manifest 建立 ≤20 blocks 的獨立 deletion batch，不得直接回用歷史分類表或舊行號。

## 4. 後續批次與執行順序

批次名稱刻意使用 `REMAIN`，避免與已完成的 TD02-01～03、TD15-01～03、R0～R3 或既有 H-10
shadow 產物混淆。每一批都必須獨立授權、實作、驗證、記錄後，才可進入下一批。

| 順序 | 建議批次 | 工作內容 | 前置條件 | 主要完成判定 |
|---:|---|---|---|---|
| 1 | TD10-REMAIN-01 | top-10 高風險函式與既有測試 coverage inventory | 取得目前測試／fixture 清單；不修改 production source | 10 個函式各有風險、owner、缺口與測試對應 |
| 2 | TD10-REMAIN-02 | 離線 fixture／golden／contract tests 補強 | REMAIN-01 清單凍結；外部資料改以 fixture 注入 | 正常、空資料與適用錯誤／timeout 分支均可重跑 |
| 3 | TD10-REMAIN-03 | TD-10 coverage closure | REMAIN-02 測試全綠；未覆蓋項目有明確理由 | 10/10 對帳完成，unit／security／E2E／quick 全綠 |
| 4 | TD13-REMAIN-01 | broad exception 靜默路徑 inventory | 固定 production Python 範圍；排除測試工具與預期攔截器 | 每個 exception 有分類、owner 與處理決策 |
| 5 | TD13-REMAIN-02 | 靜默例外最低限度 logging | REMAIN-01 確認為真正靜默；不得記錄敏感資料 | log 增加但回應、fallback、錯誤邊界不變 |
| 6 | TD13-REMAIN-03 | TD-13 行尾／可觀測性 closure | REMAIN-02 綠燈；行尾檢查與 fault injection 可重跑 | LF、靜默路徑決策完整，六層驗證通過 |
| 7 | TD19-REMAIN-01 | required-key endpoint contract audit | 目前 manifest、policy、offline fixture 可讀取 | endpoint／policy 100% 一對一，required path 有 owner |
| 8 | TD19-REMAIN-02 | required-key fault-injection verifier | REMAIN-01 完成；保留 nullable／error-only 語意 | 缺 required key FAIL，時變非關鍵欄位仍依政策容忍 |
| 9 | TD19-REMAIN-03 | TD-19 policy／fixture closure | REMAIN-02 綠燈；failure label 可辨識 | offline quick 與回歸測試全綠，產出 closure report |
| 10 | TD18-REMAIN-01 | deterministic artifact inventory／rebuild proof | Node／bundler／lockfile 與 shadow 輸出範圍固定 | 相同輸入 hash 一致，正式資產未被覆寫 |
| 11 | TD18-REMAIN-02 | bundling／minify／route split 效能評估 | REMAIN-01 綠燈；browser backend 與量測窗口可用 | bytes、request、cold／warm、source map／stack 數據可重現 |
| 12 | TD18-REMAIN-03 | 低風險入口 shadow／canary | REMAIN-02 綠燈；classic fallback 可用 | symbols、CSP、DOM／pixel／interaction、404、rollback 全綠 |
| 13 | TD18-REMAIN-04 | rollout／觀測／rollback package | REMAIN-03 綠燈；另取得正式變更授權 | 21 頁方案、監控指標、回退演練與人工放行記錄完整 |

TD-02 全站 ESM 已完成 closure；TD-03 Redis／多 worker rollout 目前仍暫時封存；TD-15 REMAIN-01～07 已 closure，沒有新的刪除批次。
本次已依使用者授權完成 TD-02、TD-10、TD-13、TD-18、TD-19；若解封 TD-03，仍須依原專屬 gate 另行授權。

## 5. 共通驗收 gate

每一個實作批次完成前都必須通過既有六層護欄：

1. Python／JavaScript 語法檢查。
2. `test_derivatives_platform.py` 單元測試。
3. `security_guardrail_check.py` 安全不變量。
4. `e2e_smoke.py` 可啟動與基本 API smoke。
5. `verify_against_baseline.py --full`：API、21 頁截圖、94 條互動路徑。
6. 涉及搬移／重構時，追加逐位元組或等價輸出比對。

另加以下共通限制：

- `escapeHtml` 仍只能有單一來源，CSP 不得加入 `unsafe-inline`／`unsafe-eval`。
- 不修改 baseline、golden、截圖或互動 manifest，除非行為變更本身獲得明確批准並另立 commit。
- 不碰 SQLite、`twse-cache.json`、執行期 cache、HAR 或建置產物。
- 每批維持最小 diff、獨立 commit；發現範圍外問題只記錄於技術債清單，不順手修復。

## 6. 各技術債專屬 gate 與 rollback

### TD-02 gate

- 895／895 前端 symbol inventory 可重現，且沒有重複全域定義。
- `escapeHtml` 呼叫數與安全 guardrail 不退化。
- 頁面初始化、listener、polling 各執行一次；錯誤注入時 fallback 行為明確。
- API schema、DOM、pixel、interaction、local 404 與嚴格 CSP 全部通過。
- rollback 順序：停用 ESM island → 回到 TD18 minified bundle → 必要時回到既有 classic script 順序。

### TD-03 gate

- 真實 Redis PING／TTL／斷線／timeout／重連與 JSON-safe bucket 有測試證據。
- 雙 worker 下 rate limit、single-flight、lease takeover、fencing 與錯誤 fail-closed 行為可重現。
- 有 p50／p95／p99、錯誤率、fallback 次數與觀測窗口記錄。
- rollback rehearsal 成功，且人工放行記錄明確。
- rollback 順序：關閉共享狀態模式 → 還原 process-local safe mode → 還原單 worker；不修改資料庫或正式 cache。

### TD-15 gate

- 每個待刪規則都有最新檔案／行號或 hash、selector、HTML／JS／runtime 三層證據。
- candidate-only 與 grouped／responsive／state／dynamic／status／direct-reference 規則分開處理。
- 每批最多 20 個規則或同等審查範圍；刪除前後均可用 reverse diff 還原。
- 21 頁、94 條互動、截圖／DOM／console／API 檢查全部無回歸。
- 任一證據不完整即保留規則，並把原因寫入 manifest，不以「未搜尋到」代替證明。

### TD-10 gate

- top-10 高風險函式清單、既有測試對帳、fixture／golden／contract test 與未覆蓋理由均可重現。
- 正常、空資料與適用的格式異常、timeout、上游錯誤、fallback 分支均有測試證據。
- 測試只使用離線 fixture／mock，不因即時資料源暫時可用而產生非 deterministic 結果。
- 不修改 production 回應契約或 baseline 來讓新增測試通過；unit、security、E2E、quick baseline 全綠。

### TD-13 gate

- production Python broad exception inventory 完成分類，所有靜默路徑都有補 log、保留說明或另立工單的決策。
- log 不含 token、cookie、個資、完整外部回應或敏感 query；原有 response／fallback／錯誤邊界維持不變。
- `.gitattributes` 行尾政策維持 LF；不以整檔格式化製造無關 diff。
- 修改過的 exception path 通過 fault-injection、unit、security、E2E 與 baseline 驗證。

### TD-18 gate

- shadow build 使用固定 lockfile／輸入清單／版本，重建 artifact 與 source map hash 可重現，且不覆寫正式資產。
- 效能比較包含 bytes、request count、cold／warm latency 與錯誤追蹤性；browser backend 不可用時不得宣稱實測完成。
- canary 保持 global symbol／script order、`escapeHtml` 單一來源、CSP、local asset 404、DOM／pixel／interaction 與 classic fallback。
- 正式 HTML、CSP、Service Worker、cache、部署與 asset version 變更必須有獨立授權、觀測窗口與 rollback rehearsal。

### TD-19 gate

- baseline manifest 每個 endpoint 與 required-key policy 一對一，required path、nullable／empty 語意與 error-only policy 有 owner。
- 故障注入移除 required key 必須 FAIL；值為 null／空集合與新增非關鍵 key 依明確契約處理。
- verifier failure label 能區分設定缺漏、程式碼回應格式回歸與外部資料源失敗。
- offline fixture、unit、security、E2E 與適用的 full verify 全部通過；不以更新 baseline 消除缺欄位差異。

## 7. 明確排除事項

本文件不授權下列行動：

- 全面 tree-shaking、移除 classic fallback 或收斂 transitional bridge。
- 取得／建立正式 Redis、改變正式 worker 數、修改 `Procfile`／`render.yaml` 或部署入口。
- 批量刪除 CSS／JS、以舊候選清單直接重跑刪除。
- TD-10：不以增加測試數量、更新 baseline 或即時外部資料成功取代 top-10 特性測試證據；不因補測試順手修改 production 行為。
- TD-13：不做整檔格式化、全域 broad `except` 改寫或記錄敏感資料；不把預期 fallback 強制改成例外拋出。
- TD-18：本次已授權並完成 minified asset、版本化 cache、Service Worker version 與正式 HTML wiring；未修改 CSP、Procfile、render.yaml 或 worker 數，classic fallback 未移除。
- TD-19：不把所有 response key 強制列為 required，不移除 structure-only 的時變欄位容忍，也不以 baseline 更新掩蓋 required-key failure。
- 更新任何 baseline／golden／截圖／互動基準來掩蓋回歸。

## 8. 下一步授權格式

本文件規劃與本次授權批次均已完成；後續若要重開新批次，應一次只授權一個批次，例如：

> 授權執行下一個獨立 REMAIN 批次

本次 `TD10-REMAIN-01～03`、`TD13-REMAIN-01～03`、`TD18-REMAIN-01～04`、
`TD19-REMAIN-01～03` 已完成驗證並回寫證據；後續若涉及正式 HTML／資產／CSP／Service Worker／cache／部署的變更，仍須另附明確變更授權。

執行前仍需確認該批次的外部依賴與可回退路徑；若條件不足，應停在 preflight 並回報阻塞原因，不以本機模擬結果宣稱完成。

## 9. 依據文件

- `docs/TD02_TD15_TD18_followup_plan_2026-08-31.md`
- `docs/TD02-02_module_boundary_design_2026-08-31.md`
- `docs/TD03_H11_redis_rollout_deferred_2026-08-31.md`
- `docs/TD15_residual_candidates_plan_2026-08-31.md`
- `docs/TD稽核清單.md`
- `docs/REFACTOR_SUMMARY.md`
- `regression/verify_against_baseline.py`（TD-19 required-key policy／offline fixture）
- `技術債改善計畫_V2_2026-08-30.md`
