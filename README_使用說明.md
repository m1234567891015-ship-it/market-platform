# Market Pulse 技術債重構套件

產出日期:2026-07-16
稽核對象:market-platform-Backup_1_.zip(V1.0 R6,2026-07-12 快照)

---

## 套件內容

```
MarketPulse_重構套件/
├── README_使用說明.md           ← 本檔案
│
├── 放入專案根目錄/               ← 整個資料夾內容直接複製到專案根目錄
│   ├── .gitignore               版控排除規則(TD-04)
│   ├── .gitattributes           行尾統一 LF、.bat 保留 CRLF(TD-13)
│   ├── .editorconfig            編輯器層行尾與縮排設定
│   ├── SETUP_GIT.bat            git 一鍵初始化腳本(雙擊執行)
│   ├── CLAUDE.md                Claude Code 專案設定(37 行精簡版)
│   ├── .claude/
│   │   └── settings.json        權限 deny + 三層 hooks 防護
│   └── docs/
│       └── 工單00_行為基準驗證系統.md   重構前必做的驗證工單
│
└── 參考文件/                     ← 給人看的,不用放進專案
    ├── MarketPulse_技術債稽核_2026-07-16.xlsx
    │     6 個工作表:債項清單(13 項含行號)、總覽、
    │     大型函式(21 個)、快取與鎖(37 項)、Nav分歧、正面盤點
    └── 技術債稽核對比報告_Claude_vs_ChatGPT.docx
          兩份稽核報告的對比評估(3 頁)
```

---

## 安裝步驟(5 分鐘)

1. **複製檔案**:將「放入專案根目錄」內的**全部內容**
   (含 `.claude` 和 `docs` 資料夾)複製到 app.py 所在的專案根目錄。
   > 檔案總管請開啟「顯示隱藏的項目」,否則看不到 . 開頭的檔案。

2. **初始化版控**:雙擊 `SETUP_GIT.bat`。
   腳本會自動:git init → 排除資料檔 → 統一行尾 → 建立初始 commit。
   完成後 `derivatives-platform.sqlite3`(60MB)與 `twse-cache.json`
   仍在原地,只是不進版控。程式碼零修改。

3. **驗證 Claude Code 設定**:在專案目錄開啟 Claude Code,
   - 問「這個專案的測試指令是什麼」→ 答得出 unittest 指令 = CLAUDE.md 生效
   - 叫它讀 derivatives-platform.sqlite3 → 被拒絕 = settings.json 生效

---

## 執行順序(關鍵:順序不可顛倒)

| 階段 | 內容 | 給 Claude Code 的指令 | 模式 |
|------|------|----------------------|------|
| 0 | 版控初始化 | (人工雙擊 SETUP_GIT.bat) | — |
| 1 | **工單 00:行為基準** | 讀取 docs/工單00_行為基準驗證系統.md,完整執行,達成所有驗收標準後回報 | 可全自動 |
| 2 | TD-10 特性測試 | 為稽核清單「大型函式」表前 10 個函式建立特性測試,跑到全綠 | 可全自動;golden file 需人工抽查 |
| 3 | 速贏包 TD-06/07/08/09/11 | 每項一個 session,開場貼稽核清單的行號座標 | 可全自動(每 TD 一個 branch) |
| 4 | TD-05/12 fetcher registry | 86 個 fetch_* 分批收斂,每批 10-15 個 | 可全自動 |
| 5 | TD-01/02 巨石拆分 | 後端分層 → 前端 ES modules | 工單 00 護欄下可自動;建議 Plan mode 先審計畫 |

每個 TD 的完成定義(Definition of Done):
- `python -m unittest test_derivatives_platform.py` 全綠
- `python regression/verify_against_baseline.py --full` 全綠
- 任一失敗不得 commit

---

## 人工檢查點(每次約 15 分鐘)

即使全自動執行,以下三個時間點請親自看一眼:

1. **工單 00 完成時**:抽查 baseline/screenshots/ 的截圖是否為正常畫面
   (基準若是壞的,之後所有比對都在保護錯誤的行為)
2. **TD-10 完成時**:抽查 2-3 個 golden file 的數字與實際市場資料是否吻合
3. **每階段結束時**:開網站點 5 個主要頁面確認會動 + 看驗證報告

---

## 安全機制總覽(已內建,無須額外設定)

| 機制 | 位置 | 作用 |
|------|------|------|
| 資料檔封鎖 | settings.json permissions.deny | 禁止讀寫 sqlite3 / twse-cache.json |
| 危險命令攔截 | PreToolUse hook | 阻擋 rm -rf、DROP TABLE、force push |
| 語法即時檢查 | PostToolUse hook | 每次編輯 .py 後強制 py_compile |
| 回合測試 | Stop hook | 每輪結束自動跑 unittest |
| 行為基準比對 | 工單 00 產出 | API golden file + 21 頁前端檢查 + 截圖比對 |
| 安全不變量 | CLAUDE.md + verify 腳本 | escapeHtml 數量、參數化 SQL、CSP 不可退化 |

基準凍結原則:比對失敗時,修的是程式碼,不是基準。

---

## 時程預估

- 分級自動化(建議):機器 2-3 天 + 人工檢查點合計約 2 小時
  + 前端拆分半自動 3-4 天
- 全人工審查:10-16 個工作天(兼職節奏 4-6 週)
- 若階段 5 降級為「新碼進新模組、舊碼漸進遷移」:總時程約 7-10 天
