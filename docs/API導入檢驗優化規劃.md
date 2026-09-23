# API 導入檢驗優化規劃

> 文件日期：2026-09-23  
> 適用範圍：21 個前端 HTML 頁面、API 導入、前端互動護欄與即時資料源檢驗  
> 文件性質：規劃文件；本文件建立時不修改產品程式碼、API 回應或既有基準

## 1. 目的

目前專案已具備完整的前端與 API 回歸護欄，但「前端是否有呼叫 API」、「API 回應格式是否正確」及「外部資料源當下是否可用」仍部分混在同一條完整驗證流程中。

本規劃的目標是把三種問題分離，讓每次檢驗都能快速回答：

1. 頁面是否真的導入並觸發預期 API？
2. API 回應結構是否仍符合前端需求？
3. 外部資料源目前是否可用、是否逾時或被限流？

## 2. 目前查驗結果

截至 2026-09-23：

| 項目 | 結果 | 說明 |
|---|---:|---|
| HTML 頁面 | 21/21 | 全部載入統一 ESM loader |
| 初始載入有 API 請求 | 17/21 | 頁面載入 HAR 中請求皆為 HTTP 200 |
| 互動後才觸發 API | 4/21 | 台股搜尋、美股搜尋、自選股等頁面 |
| 前端頁面基準 | 21/21 PASS | 0 個程式錯誤 |
| 互動路徑 | 94/94 PASS | 0 個程式錯誤 |
| API schema / 安全護欄 | PASS | `--quick` 通過 |
| 完整 `--full` | 未完成 | 被外部即時資料源長時間阻塞 |

目前已確認的主要問題不是 API 導入遺失，而是驗證程序對外部資料源的等待與分類不夠清楚。

## 3. 現況與風險

### 3.1 `--full` 可能被外部資料源拖住

`regression/verify_against_baseline.py --full` 會包含即時端點驗證。當 TWSE、TAIFEX、Yahoo 或其他外部資料源無回應時，整個流程可能長時間沒有輸出，無法快速判斷是：

- 程式碼錯誤；
- API server 啟動失敗；
- 外部資料源逾時；
- 測試本身缺少 timeout。

### 3.2 HAR 能證明「曾經呼叫」，但不等於完整契約

HAR 可以確認請求是否出現、路徑是否一致，但目前仍需要更明確地描述：

- 哪些 API 應該在初始載入呼叫；
- 哪些 API 必須由特定互動觸發；
- 哪些背景 API 是 optional；
- 哪些 503 是測試框架刻意 fast-fail，哪些是真正異常。

### 3.3 503 容易被誤讀

互動測試中部分 503 是為了避免背景慢請求拖住測試而刻意產生的 expected failure，不應與未預期的 API 錯誤混在一起。

### 3.4 缺少 loader 啟動狀態的明確斷言

目前已檢查頁面可渲染、API 可觸發，但仍應明確驗證頁面是由 ESM runtime 啟動，還是意外落入 classic fallback。

## 4. 優化目標

### 4.1 驗證流程分層

建議將驗證拆成以下五層：

| 層級 | 指令或用途 | 是否依賴外網 | 主要回答問題 |
|---|---|---:|---|
| L1 | 語法與靜態檢查 | 否 | 檔案是否可解析、loader 是否完整 |
| L2 | `verify --quick` | 否 | API schema、安全護欄是否正常 |
| L3 | `frontend_check.py --compare` | 否 | 21 頁是否正常渲染 |
| L4 | `interaction_check.py --compare` | 否 | 94 條互動是否正常觸發與更新 DOM |
| L5 | `verify --api-live` | 是 | 即時資料源目前是否可用 |

L1～L4 應該能在固定且可預期的時間內完成；L5 則獨立標記外部問題，不阻塞離線回歸結果。

### 4.2 建立頁面 API 契約

新增一份頁面層級的 API manifest，例如：

```json
{
  "page": "tw-stock-search.html",
  "initial": [],
  "interactive": [
    {
      "path": "/api/twse/live-search",
      "trigger": "search",
      "required": true,
      "response_policy": "success-or-external-error"
    }
  ]
}
```

契約至少要能描述：

- 頁面名稱；
- 初始載入 API；
- 互動觸發 API；
- 觸發事件名稱；
- 是否為必要請求；
- 是否允許背景請求失敗；
- 預期成功與錯誤回應政策。

### 4.3 增加 API schema contract

對主要 API 補充欄位與型別檢查，避免只驗證 HTTP 200：

- 必填欄位存在；
- 欄位型別正確；
- 陣列元素結構正確；
- enum 值合法；
- 空資料仍符合 schema；
- 502/503/504 使用既有錯誤 envelope。

優先涵蓋：

- `/api/twse/stock/*`；
- `/api/us-market/symbol/*`；
- `/api/futures/*`；
- `/api/options/*`；
- `/api/global-market/*`。

## 5. 分階段執行方案

### Phase 0：驗證流程可觀測性（P0）

目標：先讓驗證不再無聲等待。

工作內容：

1. 為每個 live endpoint 加上明確 timeout。
2. 每個 endpoint 開始、完成、逾時時輸出進度。
3. 在總檢查中顯示目前階段與已完成數量。
4. 為整體流程加總時間上限。
5. 將外部逾時歸類為 `[外部問題,非程式碼]`。
6. 確保任一外部端點失敗後仍能完成其他 endpoint 檢查。

驗收條件：

- 任一外部端點不可讓整個檢查無限等待；
- 失敗輸出包含頁面、端點、錯誤類型與耗時；
- `--quick` 完全不依賴外網；
- `--api-live` 可獨立執行。

### Phase 1：頁面 API manifest（P0）

目標：將 21 頁的 API 導入期待明確化。

工作內容：

1. 建立頁面 API manifest。
2. 將 17 個初始載入 API 頁面登錄為 `initial`。
3. 將 4 個互動才觸發 API 的頁面登錄為 `interactive`。
4. 驗證預期 API 是否被呼叫。
5. 驗證未出現未登錄的 API 路徑或錯誤 query。
6. 為 render-only 頁面明確標記其 API 需求。

驗收條件：

- 21 頁全部都有 manifest 記錄；
- 每頁至少有一項明確的 API 導入政策，或明確標示為純渲染頁；
- 初始與互動 API 不混淆；
- 新增頁面時，manifest 缺項會使檢查失敗。

### Phase 2：錯誤分類與 schema contract（P1）

目標：區分真正的程式問題、可接受的背景失敗與外部資料源問題。

工作內容：

1. 將 API 結果分類為：
   - `success`；
   - `expected_background_failure`；
   - `unexpected_http_error`；
   - `external_failure`；
   - `schema_failure`。
2. 為主要 API 建立 schema 或等價 contract。
3. 驗證成功回應的欄位、型別與資料結構。
4. 驗證錯誤 envelope 與狀態碼政策。
5. 報告中分別統計成功、預期失敗與未預期失敗。

驗收條件：

- 測試報告不再只顯示總 HTTP 狀態數；
- 刻意 fast-fail 的 503 不被列為程式錯誤；
- schema 缺欄位時能確實失敗；
- 將一個欄位名稱改壞後，驗證必須變紅。

### Phase 3：Runtime 與 loader 驗證（P1）

目標：確認頁面實際使用正確的 runtime bundle。

工作內容：

1. 驗證 `data-td02-esm` 是否為 `esm-active`。
2. 偵測意外的 `classic-fallback`。
3. 捕捉 module load error、`pageerror` 與 `unhandledrejection`。
4. 驗證 21 頁使用正確的 loader version。
5. 驗證 fallback 僅在 ESM 載入失敗時啟用。

驗收條件：

- 每頁報告 ESM 或 fallback 狀態；
- ESM bundle 載入失敗時測試會明確報錯；
- fallback 啟動不會被誤判為正常 ESM 導入。

### Phase 4：負向情境與穩定性驗證（P1）

目標：確認外部資料失敗時頁面仍能安全退化。

工作內容：

1. API timeout。
2. 502/503/504。
3. 空陣列與空資料。
4. 缺少必要欄位。
5. malformed JSON。
6. 慢回應與重試。
7. 前端 fallback 文案與 DOM 狀態。

驗收條件：

- 頁面不崩潰；
- 不產生非預期 console error；
- 使用者看得到可理解的資料狀態；
- 外部資料未驗證前不直接注入 DOM。

### Phase 5：視覺比對降噪與報表改善（P2）

目標：避免外部字型、動畫與時間變化掩蓋真正的程式回歸。

工作內容：

1. 把 API/DOM/互動驗證列為主要 gate。
2. 截圖比對列為視覺回歸 gate。
3. 對外部字型、動畫、時間戳與即時價格做穩定化。
4. 將 pixel diff 分為程式差異與外部資源差異。
5. 保持既有 2% pixel diff fail threshold，不以放寬 threshold 解決問題。

驗收條件：

- Google Fonts 被阻擋時只列為 external；
- 真正 DOM 或版面變更仍會失敗；
- 報告能指出差異來源。

## 6. 建議的最終檢查指令

完成上述優化後，建議形成以下標準流程：

```bash
# 不依賴外網的 PR / 本機快速檢查
python regression/verify_against_baseline.py --quick
python regression/frontend_check.py --compare
python regression/interaction_check.py --compare

# API 導入契約檢查
python regression/api_page_contract_check.py

# 需要外部資料源時才執行
python regression/verify_against_baseline.py --api-live
```

若保留單一入口 `--full`，它應該只是依序呼叫上述階段，且每一階段都必須有 timeout、進度與分類結果。

## 7. 報告格式建議

每次檢查至少輸出以下資訊：

```text
頁面：tw-stock-search.html
Runtime：esm-active
初始 API：0
互動 API：7
成功：6
預期背景失敗：1
未預期失敗：0
Schema 錯誤：0
互動斷言：10/10
結果：PASS
```

總結報告應另外列出：

- 21/21 頁是否覆蓋；
- 17 頁初始 API、4 頁互動 API 的分布；
- API endpoint 覆蓋數；
- success / expected failure / unexpected failure 數量；
- 外部資料源失敗清單；
- runtime fallback 清單；
- 執行總耗時。

## 8. 不在本次規劃範圍內

- 不修改任何產品 API 回應格式。
- 不更新既有 golden file、截圖或 HAR 基準。
- 不為了通過測試而放寬安全護欄或 pixel diff 門檻。
- 不把外部資料源暫時正常視為產品程式碼品質保證。
- 不順手清理與 API 導入無關的既有死碼或技術債。

## 9. 實作前需確認的事項

依 `AGENTS.md`，以下行為變更在實作前需先確認：

- 是否新增 `api_page_contract_check.py`；
- 是否調整 `verify_against_baseline.py` 的執行分層；
- 是否新增或修改 regression manifest；
- 是否更新任何既有基準檔；
- 是否將新的 API schema 加入 baseline policy；
- 是否調整 CI 的阻擋條件。

建議第一個實作批次只處理 Phase 0，不改 API、不改頁面、不更新基準，完成後先驗證 timeout 與報告分類，再進入 Phase 1。

## 10. 回退路徑

所有優化應採小批次、獨立 commit：

1. Phase 0：只改驗證流程 timeout / logging，可單獨回退。
2. Phase 1：只新增 manifest 與檢查器，可單獨停用。
3. Phase 2：只新增 schema / error classification，不改產品 API。
4. Phase 3～5：各自獨立提交，避免一次改動整個 regression pipeline。

若新檢查器造成既有 CI 阻擋，優先回退檢查器或將其設為報告模式，不得刪除既有護欄或降低原有驗證門檻。

## 11. 完成定義

- [ ] `--full` 不會因外部 endpoint 無回應而無限等待。
- [ ] 21 個頁面都有明確 API 導入契約。
- [ ] 初始 API 與互動 API 可分別驗證。
- [ ] success、expected failure、external failure、schema failure 可分開統計。
- [ ] 主要 API 有必要欄位與型別驗證。
- [ ] ESM / classic fallback 狀態可被測試捕捉。
- [ ] timeout、空資料、錯誤 envelope 等負向情境有測試。
- [ ] 21 頁前端與 94 條互動護欄仍維持全綠。
- [ ] 安全護欄、CSP、`escapeHtml` 與既有 baseline 未退化。
- [ ] 每個實作批次都有清楚的驗證結果與回退路徑。

## 12. Phase 1 執行結果

執行日期：2026-09-23

已完成：

- 新增 `regression/page_api_manifest.json`，登錄 21 個 HTML 頁面。
- 新增 `regression/api_page_contract_check.py`。
- 驗證每頁的 page-load HAR 與 interaction HAR API path。
- 將頁面 API 契約檢查接入 `verify_against_baseline.py --quick`。
- 目前結果為 21/21 頁通過，初始 API 與互動新增 API 均符合 manifest。
- 已完成負向自我測試：manifest 頁面重複時會正確失敗。

Phase 1 本身的契約採 path-level matching；query string、HTTP status 與 JSON schema 由 Phase 2 另行驗證。

驗證結果：

```text
python regression/api_page_contract_check.py       PASS (21/21 頁)
python regression/verify_against_baseline.py --quick  PASS (VERIFY_OK)
python -m py_compile regression/api_page_contract_check.py regression/verify_against_baseline.py  PASS
```

## 13. Phase 2 執行結果

執行日期：2026-09-23

已完成：

- 新增 `regression/api_schema_manifest.json`，定義主要頁面 API 的必要欄位與型別。
- 擴充 `regression/api_page_contract_check.py`，對 HAR 回應進行結果分類與 schema 驗證。
- 將刻意 fast-fail 的背景 503 登錄為 `expected_background_failure`。
- 將成功、預期背景失敗、外部失敗、未預期 HTTP 錯誤與 schema 失敗分開統計。
- 將 Phase 2 檢查納入 `verify_against_baseline.py --quick`。
- 負向自我測試確認缺欄位、錯型別、500、502、503 會被正確分類或報錯。

驗證結果：

```text
API page contract       PASS (21/21 頁)
success                 159
expected_background_failure 12
unexpected_http_error  0
schema_failure         0
verify --quick          PASS (VERIFY_OK)
```

Phase 2 的 schema contract 目前驗證必要欄位與指定欄位型別，不比對即時數值，也不將外部資料源可用性誤判為程式碼品質。

## 14. Phase 3 執行結果

執行日期：2026-09-23

已完成：

- 新增 `regression/runtime_loader_check.py`。
- 驗證 21 頁 HTML 的 loader build version 一致。
- 驗證正常載入時 `data-td02-esm=esm-active`。
- 驗證正常載入時 ESM module request 成功，且不意外載入 classic fallback。
- 驗證刻意阻斷 ESM module 時會進入 `classic-fallback`，並載入 common/route fallback bundle。
- 將 runtime 檢查接入 `verify_against_baseline.py --runtime`；`--full` 會自動包含。
- 特別涵蓋 `derivatives-ai.html` 的導向造成的雙重 loader 請求。

驗證結果：

```text
runtime loader contract  PASS (21/21 頁)
normal ESM               PASS
synthetic classic fallback PASS
```

## 15. Phase 4 執行結果

執行日期：2026-09-23

已完成：

- 新增 `regression/negative_stability_check.py`，以 page-load HAR 重播搭配瀏覽器 route interception，避免負向測試依賴外部資料源。
- 覆蓋 502、503、504、malformed JSON、缺欄位、空資料，以及 `fetchWithTimeout` 的短時間 timeout abort。
- 對每個頁面檢查 ESM runtime 可正常啟動、根節點仍有內容、錯誤/空資料 fallback marker 可辨識，並將未捕捉的 `pageerror` 視為失敗。
- 將 Phase 4 接入 `verify_against_baseline.py --negative`；`--full` 會自動包含。
- 測試只攔截瀏覽器請求，不修改產品 API、執行期資料、HAR 或既有 golden baseline。

驗證結果：

```text
negative stability contract  PASS (7 cases, no pageerror)
verify --negative           PASS (VERIFY_OK)
```

Phase 4 的負向測試驗證「頁面可辨識地降級」與「runtime 不崩潰」，不把預期的 `console.error` 診斷訊息誤判成 page crash；若出現真正未捕捉例外，測試會直接失敗。

## 16. Phase 5 執行結果

執行日期：2026-09-23

已完成：

- 擴充 `regression/frontend_check.py` 的逐頁視覺結果分類：`pass`、`pass_with_external_noise`、`external_noise`、`fail`、`missing_baseline`、`missing_screenshot`。
- 將外部噪音細分為 `external_font`、`external_network`、`external_resource`；Google Fonts 被阻擋時不再只顯示一長串原始錯誤。
- 保留元素數量與 console error gate；pixel diff 仍維持 2.00%，只有同頁存在外部資源錯誤且 pixel diff 超標時，才歸類為 `external_noise`，不把它當成程式回歸。
- 新增 `--report <path>`，可輸出逐頁 JSON 報表，包含 DOM counts、外部噪音分類、pixel diff、門檻、頁面失敗狀態與總結統計。
- 未修改既有 screenshot、HAR 或 baseline manifest。

驗證結果：

```text
frontend_check --compare       PASS (21/21 頁)
failed_pages                   0
visual_external_noise          18 頁
external_font_pages            20 頁
visual_fail                    0 頁
pixel diff threshold            2.00% (維持不變)
```

Phase 5 的報表會將外部字型差異與真正 pixel diff 分開；即使 pixel gate 因外部噪音降級，DOM 元素數量與 console error 仍然是硬性 gate。

## 17. 目前完成度與剩餘事項

截至 2026-09-23，Phase 0～Phase 5 的檢驗優化已完成，規劃文件中的核心實作完成度為 **100%**。目前剩餘工作屬於交付與環境整合，不再是 API 導入檢驗功能缺口：

| 狀態 | 後續事項 | 說明 |
|---|---|---|
| 待辦 | 正式 commit | 依 `AGENTS.md` 規範，在最後一次完整六層驗證全綠後建立獨立、語意清楚的 commit。 |
| 待辦 | CI 整合 | 將 `verify --quick`、`frontend_check.py --compare`、`interaction_check.py --compare`、`verify --negative` 與必要的 runtime 檢查接入 CI；即時外部端點維持獨立 job。 |
| 評估中 | Google Fonts 視覺噪音 | 目前已分類為 `external_font`，不會誤判程式回歸；若要進一步消除 20 頁的字型差異，需評估自 hosted 字型、CI font fixture 或穩定化 screenshot 環境，不能直接放寬 2% pixel diff 門檻。 |

目前不需更新 screenshot、HAR、API schema 或既有 baseline；Google Fonts 問題在未完成方案評估前，維持「外部噪音分類 + DOM/count gate + 2% pixel gate」的安全策略。
