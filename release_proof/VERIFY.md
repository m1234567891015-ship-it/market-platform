# release_proof/ 驗證指引

本目錄下的檔案讓外部審查者能不依賴原始工作目錄,獨立覆核交付內容:

- `git-log-oneline.txt`:`git log --oneline` 的完整輸出,可與獨立 clone 出來的
  repo 比對行數與內容逐行一致。
- `git-tag-proof.txt`:`git show-ref --tags` 輸出,加上
  `v1.0-refactor-complete` tag 指向的 commit hash。
- `market-platform-full-history.bundle`(交付包根目錄,`.gitignore` 排除、
  不進版控,需要時本機執行 `git bundle create market-platform-full-history.bundle --all`
  重新產生):單一檔案含完整 repo 歷史與所有 tag,可獨立 `git clone` 還原。

## 重要:逐檔 SHA 比對的執行順序

若要對 `build_portable_package.py` 產出的交付包做逐檔 SHA-256 比對(確認交付
包內容與預期一致、未被竄改),**必須在執行任何測試之前**進行,或明確排除
以下兩類項目:

- **`__pycache__/`**(含 `derivatives/__pycache__/`)——執行
  `python -m unittest test_derivatives_platform.py`(不論直接執行,或透過
  `verify_release_integrity.py`/`portable_check.py` 間接觸發)會 import 多個
  模組,Python 產生 `.pyc` bytecode cache 是正常且預期的副作用,不代表交付
  包被竄改。
- **`twse-cache.json`**——測試套件對資料庫(`derivatives-platform.sqlite3`)
  有做 tempfile 隔離(見 `test_derivatives_platform.py` 的 `setUpClass`),
  但對快取檔沒有相同的隔離機制;執行測試時若觸發 `cache.py` 的
  `save_disk_cache`,會直接改寫執行目錄下的 `twse-cache.json`(見
  `docs/TD稽核清單.md` TD-24)。這不代表交付包本身不自洽,是測試執行的
  既有副作用。

**建議順序**:先在交付包剛解壓、尚未執行任何 `.py` 之前做逐檔 SHA-256 比對,
再執行測試/驗證腳本。反過來做(先跑測試,再比對 SHA)會因為上述兩個副作用
產生假警報,誤判交付包「不自洽」,反而讓自證文件失去可信度。

另見 `docs/TD稽核清單.md`:
- TD-23:`app.py:117` 的 `DERIVATIVES_STORE.initialize()` import-time 建庫副作用。
- TD-24:clean-package 驗證流程執行測試套件的 `__pycache__`/`twse-cache.json` 副作用。
