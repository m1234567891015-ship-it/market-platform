# TD-RELEASE-v2 執行指引（供 Claude Code 在真實 repo 執行）

- 本文件產出環境：沙盒（無 `.git`、僅有兩份 ZIP 快照），僅用於**查證與規格制定**，不做實際 commit。
- 實際修復、commit、驗證一律在 Claude Code（有 `.git`、有 Flask）執行。
- 修復流程一律遵循：**characterize → rewrite → prove equivalence**。不做未經驗證的批次改動。
- GPT 修復候選 ZIP 不採用，本輪修復為團隊自行實作。

---

## 前提：沙盒查證已確認的事實（可直接信任，不需重查）

| 查證項 | 結果 |
|---|---|
| 兩份 ZIP SHA-256 | 與稽核報告一致，非調包：<br>原始版 `d7c8c454b22c763532be7f911e8c40e9125343ac3cef48cfd85dc9bb9d76a841`<br>新版 `69284510cc8c5c32842bdd6feddf211ec3d5a2bce6c18cd21282783540f0c16b` |
| .git / bundle | 兩份 ZIP 都沒有 `.git`（符合預期，ZIP 本來就是快照，不是 repo clone） |

---

## F-01：復原 3 個 tests/fixtures（P1）

**Characterize（已完成，於沙盒）：**
- 原始版 `tests/fixtures/` 確實存在 3 個檔案，且新版 `test_derivatives_platform.py` 有 3 處硬編碼引用相同路徑：
  ```
  Path("tests/fixtures/taifex_txo_sample.html").read_text(...)
  Path("tests/fixtures/taifex_futures_oi_sample.html").read_text(...)
  Path("tests/fixtures/twse_market_sample.json").read_text(...)
  ```
- 新舊版測試邏輯逐字比對後**無差異**（只有行號因測試從 42→115 條而位移），排除「格式升級導致舊 fixture 過時」的可能。
- 新版全庫搜尋確認這 3 個檔名**完全不存在**於任何路徑（非搬移、非改名，是打包遺漏）。
- 原始版 3 個檔案的基準雜湊（供比對，確保復原的是「真檔案」而非重新生成）：

  | 檔案 | 大小 | SHA-256 |
  |---|---|---|
  | `taifex_txo_sample.html` | 852 B | `5810827e29e452582e82f48d0d424e342e867f1a9e54735974c7b85e629b7c6e` |
  | `twse_market_sample.json` | 1183 B | `4eaad3e4850c634c7dcfc54e8e4cad9faccf09d957d0989a89512dbe7553be43` |
  | `taifex_futures_oi_sample.html` | 613 B | `337dbf74db4314e90ec597519f8c7c12b5991bea531d952b469cda7f80d48c5d` |

**Rewrite（Claude Code 執行）：**
1. 從 repo 的 git 歷史（refactor 前的 commit，或 `v1.0-refactor-complete` 之前）直接 `git show <commit>:tests/fixtures/<file>` 取出原檔，而不是從這次上傳的原始版 ZIP 手動複製——**理由：repo 內的歷史版本才是可被 git provenance 驗證的來源**，ZIP 只是輔助佐證。
2. 用上表雜湊核對 `git show` 取出的內容與本次查證雜湊一致；若不一致，代表 repo 內該檔案歷史上就有過改動，需要另外確認要復原到哪一版。
3. 補回 `tests/fixtures/` 目錄，加入 portable 打包的 allowlist（見 F-02）。

**Prove equivalence：**
- 乾淨解壓/clone 目錄下跑 `python -m unittest test_derivatives_platform.py`，115 條全數收集不再有 `FileNotFoundError`，且結果應與現有 CI 認可的通過數一致。
- 額外跑一次 `git status` 確認沒有多餘的未追蹤檔案殘留。

---

## F-02：補回 `build_portable_package.py`（P1）

**Characterize：**
- 沙盒查證：原始版 ZIP 裡**也沒有**這個檔案——README 對它的描述（`python build_portable_package.py` 產出 `market-platform-portable-optimized.zip`、依 allowlist 排除舊 release 資料夾與生成檔）在原始版和新版的 README 都存在，但兩份 ZIP 都不含這支腳本本體。
- **這代表 F-02 不是「復原」，而是「新建」**：這支腳本從未被打包進任何一次交付物，等同一份只存在文件描述、從未驗證過實作是否吻合的規格。Claude Code 端請先確認 repo 的 git 歷史裡是否曾經有這個檔案（`git log --all -- build_portable_package.py`）；如果 repo 裡也從未存在，代表這是文件先行、實作缺失，需要當作新開發項目而非復原項目來對待，優先度和風險評估要相應調整。

**Rewrite：**
1. 先跑 `git log --all --oneline -- build_portable_package.py`，回報有沒有歷史版本。
   - 若有：`git show <commit>:build_portable_package.py` 取出，再核對是否仍符合現行 `market_config.py` 的 allowlist 常數。
   - 若無：依 README 現有描述（allowlist、排除舊 release 資料夾與生成檔、輸出 `market-platform-portable-optimized.zip`）reverse-spec 出需求，比對 `market_config.py` 裡列出的 route allowlist / static asset allowlist 常數，寫成新腳本。
2. 腳本至少要能：讀 allowlist → 複製檔案到暫存目錄 → 排除 `.sqlite3`、`__pycache__`、舊 release 資料夾、快取檔 → 壓成 ZIP → 印出 SHA-256。

**Prove equivalence：**
- 在乾淨目錄執行 `python build_portable_package.py`，產出的 ZIP 用 `unzip -l` 核對內容不含 `.sqlite3`、`__pycache__`、`derivatives-platform.sqlite3` 等應排除項。
- 對產出 ZIP 做一次完整 smoke：解壓到全新資料夾、啟動 Flask、跑 `verify_release_integrity.py`（見 F-03）與 `portable_check.py`。

---

## F-03：`verify_release_integrity.py` 支援 clean-package 模式（P1）

**Characterize（已完成，於沙盒，含程式碼定位）：**

實際程式碼（`new/verify_release_integrity.py`）：

```python
DB_PATH = Path("derivatives-platform.sqlite3")

def db_snapshot(path: Path) -> dict[str, int]:
    with sqlite3.connect(path) as connection:
        queries = {
            "option_chain_snapshot_total": "SELECT COUNT(*) FROM option_chain_snapshot",
            ...
        }
        return {name: connection.execute(sql).fetchone()[0] for name, sql in queries.items()}
```

根因：`sqlite3.connect(path)` 在檔案不存在時會**靜默建立一個空檔案**，接著 `connection.execute(sql)` 對不存在的資料表 `option_chain_snapshot` 執行查詢，才真正丟出 `OperationalError: no such table: option_chain_snapshot`。這與稽核報告第 F-03 條的實測錯誤訊息完全吻合，根因確認無誤。

此腳本的設計意圖是「跑測試前後比對正式 DB 快照，確保 test suite 沒有污染正式資料」——這是有價值的安全網，不能直接砍掉，只是沒考慮「乾淨交付包裡本來就沒有 DB」這個情境（而這個情境是刻意的，新版已把 60.7MB SQLite 排除在交付物外，屬正確方向）。

**可重用的既有介面**（`derivatives_store.py`）：
```python
class DerivativesStore:
    def __init__(self, path: str | Path) -> None: ...
    def initialize(self) -> None:
        with ...:
            connection.executescript(SCHEMA_SQL)   # 只建表，不灌資料
```

**Rewrite（建議方案，Claude Code 端可調整細節但需符合以下原則）：**
1. 新增 `--clean-package` 旗標（或自動偵測 `DB_PATH.exists()` 為 False 時自動進入此模式，並在輸出中明確標註 `mode: clean_package`，避免和「正式庫比對」模式的輸出混淆）。
2. clean-package 模式下：
   - 呼叫 `DerivativesStore(DB_PATH).initialize()` 建立空 schema（只有表結構，沒有資料列）。
   - `before` 快照理論上全為 0；`db_unchanged` 的比對邏輯需要調整為「test 跑完後 mock/test 資料計數是否為 0」而不是「跑前跑後完全相等」（因為乾淨庫本來就會被測試寫入一些資料，這是預期行為，不是污染）。
   - 明確地在 JSON report 裡加一個欄位區分：`db_source: "pre_existing"` vs `db_source: "freshly_initialized_for_clean_package_check"`，避免審查者誤讀成「正式庫被驗證過」。
3. 若 `DB_PATH.exists()` 為 True（例如在有正式資料的部署環境跑），維持現有「跑前跑後比對」邏輯不變——**這條路徑不能因為這次修復而被破壞**，這正是 prove equivalence 要顧到的部分。

**Prove equivalence：**
- 情境 A（現有）：找一份帶正式資料的 DB，跑修改前/修改後的腳本，兩次的 `before`/`after`/`mock_free` 輸出應完全一致（regression 不能破壞既有行為）。
- 情境 B（新增）：全新解壓、無 `.sqlite3` 的乾淨目錄下跑，腳本不再拋 `OperationalError`，且明確回報 `clean_package` 模式與 115 tests 通過。

---

## F-04：附上 git bundle（P1）

**Characterize：**
- 目前只有 `release_proof/git-log-oneline.txt`（121 行）與 `release_proof/git-tag-proof.txt`（4 行）等文字檔佐證，這些只是文字紀錄，無法被獨立 clone 驗證，也無法排除文字檔本身被竄改的可能。

**Rewrite（Claude Code 執行，需要真實 `.git`）：**
```bash
git bundle create market-platform-full-history.bundle --all
git bundle verify market-platform-full-history.bundle
```
將 bundle 檔納入交付包 allowlist（連動 F-02 的 `build_portable_package.py`）。

**Prove equivalence：**
```bash
mkdir /tmp/bundle-verify && cd /tmp/bundle-verify
git clone /path/to/market-platform-full-history.bundle .
git log --oneline | wc -l    # 應為 121
git tag                       # 應能看到 v1.0-refactor-complete 等 4 個 tag
```
在全新目錄 clone 出來後，額外核對 `git log --oneline` 行數與 `release_proof/git-log-oneline.txt` 內容逐行一致，證明文字 proof 與真實歷史吻合，而不只是兩者各說各話。

---

## 建議執行順序（沿用稽核報告第六節，微調為配合本文件分工）

1. F-01：先確認 repo 歷史裡的 fixture 雜湊，復原並跑 115 tests
2. F-04：先產生 git bundle（風險最低、依賴最少，可提早完成建立信心）
3. F-02：確認 repo 歷史後決定是「復原」或「新建」，實作並產出乾淨 portable ZIP
4. F-03：在 F-02 產出的乾淨 ZIP 上驗證 clean-package 模式
5. 全部完成後，於乾淨解壓/clone 目錄跑一次完整 baseline（unit + security + e2e）
6. 更新 README 對齊實際檔案數、測試數、driver 版本
