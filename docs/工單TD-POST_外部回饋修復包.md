# 工單 TD-POST:外部技術回饋修復包

**來源**:一份外部技術回饋（另一 AI 實際解壓交付包並執行腳本後提出的六點觀察）。
**性質**:六點中四點確認為真、應處理；兩點為設計取捨或無損，記帳即可。
**前置**:本重構週期已封存（`v1.0-refactor-complete`）。本工單為封存後的維護增補，屬獨立的小型工單集，不影響已封存的成果。

本工單集含四個獨立項目，各自獨立 commit、獨立驗證。建議依序執行:
- TD-21|`route_scan.py` 失效修復（行為變更型:修工具）
- 文件漂移|93 → 94 同步（純文件）
- portable_check|失敗訊息改善（行為變更型:改工具）
- TD-20|release integrity 交付包模式（登記，本輪不修）
- 交付包自證證明檔（新增交付物）
- 文件精確性|「模組」用詞收緊（純文件）

---

## 項目 1|TD-21:`route_scan.py` 失效修復

**問題**:`route_scan.py` 仍只掃描 `app.py` 的 `@app.route`，但 48 條 routes 已於 TD-01 搬至 `routes_*.py`（system/global_market/twse/derivatives 四個 Blueprint）。實際執行結果:
```
total routes: 0
api routes: 0
api GET routes: 0
```
目前 baseline 驗證改用 manifest，故不受即時影響；但未來若重新執行 `capture_baseline.py`，路由掃描會回報 0 條、造成基準錯誤。這是潛伏的工具失效。

**修復要求**:
1. 修正 `route_scan.py`，掃描範圍改為 `app.py` + 全部 `routes_*.py`（涵蓋四個 Blueprint 的 route 定義）。
2. 注意 Blueprint 的裝飾器可能不是 `@app.route` 而是 `@bp.route` / `@<blueprint_name>.route`——掃描邏輯需涵蓋這些形式。
3. 修正後執行，確認正確數出 **48 條 routes**（與 TD-01 結案時的 `grep -c "@app.route"` = 0、48 條分佈於 4 Blueprint 的事實一致）。
4. 若 `capture_baseline.py` 有引用 `route_scan` 的結果，一併確認引用處在修復後行為正確。

**驗收**:`route_scan.py` 回報 route 數 == 48，且與 manifest 的端點涵蓋一致。

---

## 項目 2|文件漂移:93 → 94 同步

**問題**:TD-16 將互動基準從 93 步驟補到 94（新增法人歷史修復後的路徑）時，以下三個檔案的舊數字未同步:
- `regression/verify_against_baseline.py`
- `docs/frontend_module_map.md`
- `指令/指令18.md`

**修復要求**:
1. 將上述三處殘留的「93」更正為「94」（僅限指涉互動基準步驟數的位置，不要誤改其他語意的 93）。
2. 全 repo 再掃一次 `93`，確認沒有第四處遺漏（`grep -rn "93" --include="*.py" --include="*.md"`，人工判讀哪些是互動步驟數）。

**驗收**:全 repo 中，凡指涉互動基準步驟數者一律為 94，無殘留 93。

---

## 項目 3|`portable_check.py` 失敗訊息改善

**問題**:`portable_check.py` 將後端 stdout / stderr 都導向 `DEVNULL`，啟動失敗時只 exit 1、無任何訊息。缺少 Flask 或啟動錯誤時，使用者無從得知原因。

**修復要求**:
1. 啟動子行程時，將 stderr（及必要的 stdout）導向暫存檔而非 `DEVNULL`。
2. 啟動失敗（非零退出或 health 檢查逾時）時，輸出暫存 log 的尾端內容（例如最後 20 行）到主控台。
3. 成功時維持安靜（不污染正常輸出）。

**驗收**:故意在無 Flask 的環境或製造啟動錯誤，確認 `portable_check.py` 失敗時印出可讀的錯誤尾端，而非無訊息退出。

---

## 項目 4|TD-20 登記（本輪不修）

**問題**:`verify_release_integrity.py` 假設在「有資料庫的工作目錄」執行——它在建立資料表之前直接查詢 `option_chain_snapshot` / `ai_analysis_report` / `institutional_position`。因此對「已排除 60MB SQLite 的乾淨交付包」解壓後直接執行，會噴:
```
sqlite3.OperationalError: no such table: option_chain_snapshot
```

**定性**:排除 SQLite 是刻意的設計取捨（CLAUDE.md 明訂資料與程式碼分離），並非缺陷。此腳本目前是「工作目錄完整性檢查」，尚不是「乾淨交付包完整性檢查」。

**本輪動作**:僅登記，不修。在 `docs/TD稽核清單.md` 新增:
> **TD-20（低優先，測試/交付）**:`verify_release_integrity.py` 假設工作目錄含資料庫，查表前未先建表，乾淨交付包解壓後執行會噴 `no such table`。應區分兩種模式:(a) 工作目錄完整性檢查（現況）;(b) 交付包完整性檢查（先建 schema 或跳過資料表查詢）。

---

## 項目 5|交付包自證證明檔（新增交付物）

**問題**:先前的乾淨備份 zip 排除了 `.git`，導致「115 commits / `v1.0-refactor-complete` tag」等宣稱**無法從交付包本身獨立覆核**——只在原工作目錄成立。外部審查者無法驗證。

**修復要求**:在 repo 根目錄產生以下自證檔案，供未來連同交付包一起分發:
1. `git bundle create market-platform-full-history.bundle --all`
   （單一檔案含完整 repo 歷史與所有 tag，可 `git clone` 還原）
2. `git log --oneline > release_proof/git-log-oneline.txt`
3. `git show-ref --tags > release_proof/git-tag-proof.txt`
4. `git rev-parse v1.0-refactor-complete >> release_proof/git-tag-proof.txt`（附 tag 指向的 commit hash）

將 2-4 集中於 `release_proof/` 目錄。`.bundle` 因較大可置於根目錄或另行說明。

**驗收**:在一個全新的暫存目錄 `git clone market-platform-full-history.bundle`，確認還原後 `git log` 可見 115 commits、`git tag` 可見 `v1.0-refactor-complete`——證明交付包可獨立自證。

---

## 項目 6|文件精確性:「模組」用詞收緊

**問題**:外部回饋正確指出——前端目前是 classic script 拆檔（21 頁仍以多個 `<script src>` 載入 15 個 `js/*.js`，共享全域作用域），**並非 ES Modules**，也無 code splitting / tree shaking / bundling（那些是 TD-18）。稱「15 個 JS 模組」雖非虛報（已誠實列 TD-18），但用詞可更精確。

**修復要求**:在 `docs/REFACTOR_SUMMARY.md` 及任何對外復盤文件中，將:
- 「15 個 JS 模組」→「15 個 classic-script JS 切片（共享全域作用域，非 ES Modules;打包/tree-shaking 留待 TD-18）」
- 同理檢查 CSS 描述:「7 個 CSS 切片」用詞已精確，維持。

**驗收**:對外文件不再有可被解讀為「已完成 ES Module 化」的用詞。

---

## 統一驗證

四個修復類項目（1、2、3、5、6）各自 commit 前:
1. 若動到 `.py`:`node --check` 不適用，改 `python -m py_compile`
2. `python -m unittest test_derivatives_platform.py`（確認未影響既有測試）
3. `python regression/verify_against_baseline.py --full`（確認四層護欄仍全綠、互動基準 94）
4. 每項獨立 commit，message 註明對應項目與「回應外部技術回饋」

## 開場指令

```
讀取 docs/工單TD-POST_外部回饋修復包.md,依序執行六個項目。
項目 1/2/3/5/6 為實作(修復 route_scan、同步 93→94、
改善 portable_check 失敗訊息、產出交付包自證檔、收緊模組用詞),
項目 4 僅登記 TD-20 不修。
每項獨立 commit + verify --full 確認護欄仍全綠(互動基準 94)。
route_scan 修復登記為 TD-21。全部完成後回報。
```
