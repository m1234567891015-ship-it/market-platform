# TD-15 residual candidates 後續逐批處理規劃（2026-08-31）

## 0. 本文件定位

本文件只規劃剩餘候選的後續處理方式，**不執行 CSS／JS 刪除、不修改 baseline、不修改 runtime／HTML／CSP／部署設定**。它承接 [TD-15 CSS 分類表](td15_css_classification.md)、[TD-15 JS 分類表](td15_js_classification.md) 與既有 H-04／H-09 執行紀錄。

核心原則仍是「寧可漏刪，不可誤刪」：歷史分類中的行號與候選數不是現況刪除規格；每一個後續 batch 開始前都必須以目前磁碟內容重新產生精確 rule-block manifest。

## R0 執行結果（2026-08-31）

已執行現況 rule-block／symbol manifest 重建與歷史刪除對帳，產出 [R0 JSON manifest](TD15_residual_inventory_2026-08-31.json) 與 [R0 Markdown report](TD15_residual_inventory_2026-08-31.md)。

- 現況共有 191 個含候選 class 的 CSS rule blocks、90 個目前出現的候選名稱。
- 暫分為 39 個 `candidate-only-review`、50 個 grouped/compound review、102 個 dynamic/status/direct-reference retained；這些仍是 review queue，不是刪除清單。
- H-04-01～H-04-10／H-09-03 歷史紀錄對帳為 32 個已刪除 blocks；歷史行號不回用為現況規格。
- 現有護欄基準仍為 21 頁、94 條互動路徑；本次 R0 未修改 CSS、JS、HTML，也未更新 baseline。

R0 gate 通過。後續 R1／R2 只接受來自現況 JSON 的精確檔案、行號、selector、hash，並須先完成人工 review 才能進入刪除工具。

## 1. Residual inventory（分類快照，非現行刪除清單）

| 類別 | 分類快照 | 現在的處理決定 |
|---|---:|---|
| CSS class candidates | 216 | 重新盤點後才可進入任何 deletion queue |
| CSS ID candidates | 7 | 已核實不是目前獨立 CSS selector，不列入刪除 |
| Dynamic／prefix／HTML 產生路徑 rows | 81 | 全數保留；除非未來找到精確 generator 與 runtime 證據，不進刪除 queue |
| Grouped／compound／state／responsive residual | 12 個全數降級候選，另有 mixed blocks | 保留；只有拆出純淨 dead block 且三方證據完整時才可重新評估 |
| Candidate-only CSS blocks | 分類快照 59 個；另記錄可執行位置 220 blocks | 必須扣除既有 H-04-01～10、H-09-03 已刪 32 blocks 後，以現況重算，不能沿用舊行號 |
| JS first/second-layer snapshot | 第一層 52、第二層觀察 6 | 先重算目前 global-symbol／呼叫鏈；第二層不得直接刪除 |

### 1.1 已固定保留的範圍

- `is-*`、`ma-*`、`metric-*`、`market-ai-risk-*`、`market-risk-*`、`sector-card` 等已有動態／HTML 路徑的 rows 保留。
- `asset-*` 與其餘 `sector-*` 前綴只有 prefix 命中、尚無精確 generator 的 rows 保留；prefix 命中本身不能授權刪除。
- grouped selector 只要含任何 live class、compound dependency、`:hover`、`:focus-visible`、`.is-active`、tone class 或 responsive media override，就保留整個 rule block。
- 語義上可能代表資料狀態的 selector（例如 up/down、alert、warning、active、disabled、stale）不因預設截圖零命中而刪除。

## 2. 後續批次順序

### Batch R0：現況重建與歷史對帳（先做，唯讀）

每次開始新 deletion batch 前執行：

1. 重新解析目前 `split-01.css`～`split-07.css` 與仍存在的 legacy stylesheet，建立每個 rule block 的 file、start line、selector、media/supports context、SHA-256。
2. 對 root `pwa.js`、`derivatives-ui.js`、`service-worker.js`、`twse-data.js`、`app.js`、`js/*.js`、21 個 HTML、測試與相關 Python 做完整 selector／symbol 掃描。
3. 將歷史已刪除的 32 個 rule blocks 標成 `already-removed`；不存在的舊候選不重新列為待刪。
4. 重新檢查 static whitelist／實際載入清單，區分「production split CSS」與「未載入 legacy asset」；不可用舊文件行號直接呼叫 `delete_css_rules.py`。
5. 輸出本批候選 manifest；若 current source、baseline owner、分類文件或既有 deletion record 互相矛盾，狀態為 `blocked-for-reconciliation`，只記錄不刪除。

R0 gate：候選數、rule-block 數、檔案 hash、既有刪除紀錄與 21 頁載入清單對得上，才能進入 R1/R2。

### Batch R1：低風險 candidate-only CSS

只挑目前仍存在、整個 selector block 100% 由已確認 dead selector 組成的規則。優先順序：

1. 未被 21 頁載入、且 static whitelist／asset usage 已證明不會進 production 的 legacy stylesheet rules。
2. production split CSS 中不含 grouped branch、media override、狀態修飾與 live compound class 的結構性 rules。
3. 同一語義群組每批最多 20 個 rule blocks；若同一 selector 在不同 context 的證據不同，拆成不同 batch，不合併處理。

不把「候選 class 數」當作刪除單位；實際執行單位固定是 `(css file, exact current startLine)` rule block manifest。

#### R1-01 執行結果（2026-08-31）

已依現況 manifest 與三方證據完成 1 批、11 個 rule blocks 的刪除；全部位於未載入且不在 static whitelist 的 `assets/styles.css`。刪除後重建 manifest 為 271 個含候選 class 的 blocks、0 個 `candidate-only-review`；剩餘 grouped／compound 與 dynamic／status／direct-reference 項目轉由 R2 或 observe 處理。詳見 [R1-01 evidence](TD15_R1_01_evidence_2026-08-31.md) 與 [deletion specs](TD15_R1_01_deletion_specs_2026-08-31.json)。

#### R2-01 執行結果（2026-08-31）

已完成 1 批、8 個未載入 legacy `assets/styles.css` grouped blocks 的刪除；production `split-*.css` 的 65 個 grouped／compound blocks（含 responsive／state）全部保留。刪除後重建 manifest 為 263 個含候選 class 的 blocks、0 個 candidate-only、65 個 grouped/compound、198 個 dynamic/status/direct-reference。詳見 [R2-01 evidence](TD15_R2_01_evidence_2026-08-31.md) 與 [deletion specs](TD15_R2_01_deletion_specs_2026-08-31.json)。

### Batch R2：grouped／responsive／state 候選再評估

R2 不是預設刪除批次。只有在能先拆出 live branch、證明剩餘宣告不服務任何 live selector，且補齊 desktop／responsive／active／focus／hover 證據時，才可提出單一小組。否則維持 `observe`。

`wide`、`weighted-index-note-card`、derivatives overview card/grid、US ETF detail grouped selectors、US sector positive/negative bars，以及 futures snapshot active rules 先列保留，不列入下一個 deletion batch。

### Batch R3：JS residual re-audit

JS 先重新對齊 `td15_js_classification.md` 的 52/6 snapshot、目前 global-symbol baseline、`td15_observe_list.md` 與 H-04-11～15 既有 deletion records：

- 第一層只有在 AST unreachable、全 repo literal scan zero hit、dynamic access pattern 排除三項同時通過時才可列 deletion queue。
- 第二層觀察 symbol 維持原始碼，不加 `console.warn`，除非另取得行為變更授權。
- 任何疑似整條 dead call chain 必須連同 root、caller、callee 與 HTML／event／window 動態入口一起核對；不得只刪 leaf function。
- 每批 ≤20 symbols，刪除後更新 symbol manifest，但不得用 baseline 更新掩蓋未分類差異。

#### R3 執行結果（2026-08-31）

已完成現況 JS residual re-audit；`js/legacy-unclassified.js` 為 0 bytes、top-level declarations=0，歷史 52 個第一層與 6 個 observe symbols 在目前 HTML／JS／CSS／Python 執行來源 literal hits=0，`window[...]` dynamic sites 未命中任何歷史候選。H-04-11～H-04-15 的五條觀察鏈已完成既有整鏈重評，本批不重刪、不更新 global-symbol baseline。詳見 [R3 audit](TD15_R3_js_residual_audit_2026-08-31.md) 與 [R3 verifier](../regression/td15_js_residual_audit.py)。

## 3. 每批固定驗收與回退

每一個 R1/R2/R3 deletion batch 必須有獨立候選清單與回退點：

| gate | 必要證據 |
|---|---|
| CSS／JS static | exact current file／line、selector 或 symbol、AST／literal／dynamic scan 結果 |
| HTML／runtime | 21 頁載入清單、所有 render／event／classList／window access 路徑 |
| page behavior | 21 頁 frontend compare、94 條 interaction compare；CSS 另要求 pixel diff 零未分類差異 |
| safety | `escapeHtml`、CSP、security guardrail、static whitelist 維持 |
| syntax／tests | 受影響檔案 syntax、unit、E2E、full verify 全通過 |
| rollback | 單一 batch 可用精確反向 diff 恢復，不回退其他 dirty worktree 變更 |

固定命令：

```text
node --check <受影響 JS>
python -m unittest test_derivatives_platform.py
python security_guardrail_check.py
python e2e_smoke.py
python regression/verify_against_baseline.py --full
```

外部資料源或瀏覽器阻擋只能標記 `[外部問題]`；`[程式碼可能改動回應格式]`、pixel／DOM／interaction 差異必須停下調查，不能更新 baseline 消除。

## 4. 進入下一批的決策門

- R0 已完成；後續 R1／R2 仍不得跳過現況 manifest 與人工 review。
- 候選只依賴 prefix、舊行號或單一靜態 screenshot：不刪除。
- 任何 grouped／responsive／state／dynamic 證據不足：降級 observe。
- 一批超過 20 個 rule blocks 或 20 個 symbols：拆批。
- 驗證出現未分類差異：停止後續批次，先回退該批或修正證據；不更新 baseline。

因此，本規劃文件的 R0～R3 執行路線已完成：R1 已處理 11 個 candidate-only blocks、R2 已處理 8 個未載入 legacy grouped blocks、R3 已完成 JS residual re-audit 且無需刪除。現況剩餘 65 個 production grouped／responsive／state blocks 與 198 個 dynamic/status/direct-reference blocks，依證據不足即保留的 gate 維持 observe；只有未來出現新且完整的三方證據時，才另立不超過 20 個 rule blocks／symbols 的新批次，不直接回用舊行號或舊分類表。

## 5. 文件最終狀態（2026-08-31）

- 規劃路線：R0、R1、R2、R3 均已完成並有獨立 manifest／evidence／驗證紀錄。
- R1／R2 刪除結果：共 19 個 CSS rule blocks；刪除後完整驗證為 `VERIFY_OK`，21/21 frontend、94/94 interaction。
- R3 JS 結果：歷史 58 個符號目前 declaration、literal hit、candidate dynamic hit 均為 0，不重複刪除。
- TD-15 尚不宣稱「所有候選皆刪除」；剩餘 dynamic、status、grouped、responsive 與 state 項目只有在新證據完整時才可另批處理。

## REMAIN closure update（2026-09-01）

本規劃的後續 TD15-REMAIN-04～07 已完成：65 個 grouped／compound 與 198 個 dynamic／status／direct-reference blocks 均逐項完成 review，最終 `retain=263`、`observe=0`、`delete_candidate=0`、`blocked=0`。REMAIN-07 採 no-op closure，未執行新的 CSS deletion batch；本文件的舊 R0／R1／R2 數字保留作歷史紀錄，後續以 2026-09-01 current manifest 為準。
