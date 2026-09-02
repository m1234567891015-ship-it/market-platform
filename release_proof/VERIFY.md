# release_proof/ 驗證指引

本目錄下的檔案讓外部審查者能不依賴原始工作目錄,獨立覆核交付內容:

- `git-log-oneline.txt`:`git log --oneline` 的完整輸出,可與獨立 clone 出來的
  repo 比對行數與內容逐行一致。
- `git-tag-proof.txt`:`git show-ref --tags` 輸出,加上
  `v1.0-refactor-complete` tag 指向的 commit hash。
- `market-platform-full-history.bundle`(交付包根目錄,`.gitignore` 排除、
  不進版控,需要時本機執行 `git bundle create market-platform-full-history.bundle --all`
  重新產生):單一檔案含完整 repo 歷史與所有 tag,可獨立 `git clone` 還原。

## 重要:逐檔 SHA 比對與副作用護欄

批次 F 已移除兩項交付驗證副作用：`import app` 不再初始化
`derivatives-platform.sqlite3`；`test_derivatives_platform.py` 以暫存目錄隔離
`twse-cache.json`，`verify_release_integrity.py` 的子測試程序另設
`PYTHONDONTWRITEBYTECODE=1`。clean-package 驗證也會回報
`side_effect_db_created=false`、`cache_unchanged=true`，並在失敗時以非零狀態停止。

仍建議在交付包剛解壓、尚未執行任何 `.py` 之前做逐檔 SHA-256 比對；執行
`portable_check.py` 時應將 `DERIVATIVES_DB_PATH` 與 `MARKET_PULSE_CACHE_FILE`
指向暫存或持久化資料目錄，不要寫入程式碼目錄。

另見 `docs/TD稽核清單.md`：TD-23、TD-24 已修復。
