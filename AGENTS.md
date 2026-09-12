# AGENTS.md — Market Pulse V1.0 R6

> 本檔案是給 AI 開發代理（Codex 等）的專案工作規範，等同於 Claude Code 使用的 CLAUDE.md。
> 本專案剛完成一次為期九天、零行為回歸的大型重構（`git tag v1.0-refactor-complete`）。
> 你接手的是一個**乾淨、有完整護欄、可追溯**的 codebase。你的責任是：在不破壞既有行為的前提下開發，並讓新功能同樣受護欄保護。

---

## 0. 最重要的一條規則（先讀）

**這個專案沒有 hook 自動強制驗證。驗證靠你自律，不靠系統攔截。**

在 Claude Code 環境下，`.claude/settings.json` 的 hook 會在每次編輯後自動 `py_compile`、每回合結束自動跑 `verify`、自動攔截危險指令。**你（Codex）沒有這層自動保護。** 因此:

> **每一個 commit 之前，你必須主動、完整地跑過第 4 節的六層驗證，全綠才 commit。**
> **不准「先 commit 之後再補驗證」。不准假設「小改動應該沒問題」。**

這條規則是這個專案零回歸的核心。違反它，等於拆掉九天建起來的護欄。

---

## 1. 專案結構（重構後）

**後端**（Python / Flask，app.py 已從 15,514 行拆為 650 行薄入口）:
- `app.py` — 應用組裝、Blueprint 註冊、bootstrap、啟動入口
- `routes_system.py` / `routes_global_market.py` / `routes_twse.py` / `routes_derivatives.py` — 4 個 Blueprint，共 49 條路由
- `fetchers.py` — 外部資料抓取（86 個 fetch_*）
- `fetch_registry.py` — 宣告式資料來源 registry
- `builders.py` — 資料組裝（build_*）
- `parsers.py` — 回應解析
- `cache.py` — 快取狀態與 LRU 機制
- `security.py` — 安全標頭、rate limit、admin token
- `market_config.py` / `derivatives_store.py` — 設定與資料存取

**前端**（classic script，非 ES Modules）:
- `js/*.js` — 15 個 classic-script 切片，21 頁 HTML 以多個 `<script src>` 依序載入，**共享全域作用域**
- 載入順序即依賴順序，見 `docs/frontend_module_map.md`
- `split-01.css` ~ `split-07.css` — CSS 按原始行號位置切割（cascade 順序不可變）

**驗證/護欄**（`regression/` 目錄）:
- `verify_against_baseline.py` — 主驗證入口
- `security_guardrail_check.py` — 安全不變量
- `frontend_check.py` — 21 頁截圖
- `interaction_check.py` — 94 條互動路徑
- `test_derivatives_platform.py` — 115 個 unit test

---

## 2. 硬性規則（違反即回退）

1. **一次一個任務**。不要同時進行多個功能/修復。完成一個、驗證、commit，再下一個。
2. **禁止整檔重寫**。以最小 diff 達成目標。
3. **資料與程式碼分離**。絕不 commit `*.sqlite3`、`twse-cache.json`、`*.har`、`*.bundle` 等執行期/建置產物（`.gitignore` 已排除，不要繞過）。
4. **絕不碰 SQLite 資料庫檔的讀寫**。測試一律用 `regression/server_harness.py` 的獨立 temp 快取目錄，不碰真正的 `twse-cache.json`。
5. **每個 commit 前跑六層驗證**（第 4 節），全綠才 commit。獨立、語意清楚的 commit message。
6. **行為變更型工作，先提方案等人確認**。新增功能、修改既有行為、動驗證工具本身——這些在動手前要先說明方案、影響範圍、revert 路徑，經人確認後才執行。純粹的既有 bug 修復可直接做，但仍需第 4 節驗證。
7. **發現既有問題但不在當前任務範圍內 → 記錄，不順手修**。記入 `docs/TD稽核清單.md`，留獨立工單。

---

## 3. 安全不變量（絕不可退化）

以下是重構全程守住的安全資產，任何新開發都必須維持:

1. **SQL 全參數化**。execute() 一律用參數綁定，零字串拼接/f-string。
2. **escapeHtml 單一來源**。全專案只有一份 `escapeHtml` 定義（在 `js/core.js`）。所有輸出到 DOM 的使用者/外部資料必須經它處理。目前呼叫數有基準計數，`security_guardrail_check.py` 會檢查。
3. **CSP 不退化**。`script-src 'self'`、`frame-ancestors 'none'` 維持。**禁止**為了方便加入 `unsafe-inline` / `unsafe-eval`；**禁止**在 HTML 加 inline `<script>` 內容（`<script src>` 可以）。
4. **SSL fallback 有 production 阻擋**。`_urlopen_with_ssl_fallback` 的 gating 不可移除。
5. **安全標頭完整**。X-Frame-Options、HSTS、nosniff、Permissions-Policy 不可拿掉。
6. **debug=False、無 hardcoded secrets**。

---

## 4. 六層驗證（每個 commit 前必跑）

```bash
# 1. 語法
python -m py_compile app.py <你改過的 .py>
node --check <你改過的 .js>        # 若改了前端

# 2. 單元測試
python -m unittest test_derivatives_platform.py

# 3. 安全不變量
python security_guardrail_check.py

# 4. 端到端可啟動
python e2e_smoke.py

# 5. 完整基準（API + 21 頁截圖 + 94 條互動路徑）
python regression/verify_against_baseline.py --full

# 6. 若為搬移/重構類改動：逐位元組比對（見重構期工具）
```

**全部綠燈才 commit。** `verify --full` 的紅燈分兩種，看訊息標籤:
- `[外部問題,非程式碼]` → TWSE/TAIFEX/Yahoo 當下不可用，重跑即可，非你的錯
- `[程式碼可能改動回應格式]` → 你改到了 API 回應結構，這是真問題，必須查

---

## 5. 需要停下來等人確認的操作

以下不要自作主張，先問:
- 任何**新增功能**的實作方案（見 `docs/新功能開發規範.md`）
- 修改既有的**使用者可見行為**
- 動到**驗證工具/護欄本身**（`regression/` 下的檔案）
- 更新任何**基準檔**（golden file、截圖基準、互動 manifest）——基準凍結原則:比對失敗預設修程式碼，只有「行為變更是任務目標本身」時才更新基準，且需人確認 + 獨立 commit 說明
- 刪除任何程式碼（死碼清理有專門的三重證據流程，見 TD-15 相關文件）
- 任何會動到部署設定（Procfile / render.yaml / gunicorn 入口 `app:app`）的改動

---

## 6. 部署注意事項

- gunicorn 入口為 `app:app`。若用 Blueprint 重組，確認此入口仍有效。
- **多 worker 限制**:rate limit / 快取狀態目前是模組層 dict（TD-03 未完全外移），gunicorn 必須鎖 `--workers 1`，否則 rate limiting 會失效。
- Service Worker:前後端有相依的破壞性變更部署時，需一併遞增 `CACHE_VERSION` 強制訪客全清重建。平常獨立部署不用。

---

## 7. 領域名詞（台股）

三大法人（外資/投信/自營）、籌碼分析、融資融券、台股紅漲綠跌（與美股相反）、除權息、當沖。TWSE=證交所（上市）、TPEX=櫃買（上櫃）、TAIFEX=期交所。

---

## 8. 開發新功能的第一步

**在寫任何程式碼之前，先讀 `docs/新功能開發規範.md`。** 它規定了新功能如何同步納入護欄——不遵守的話，新功能會落在護欄視線外（現有護欄是為「舊行為不變」設計的，看不到新東西）。這是本專案對新開發最重要的要求。
