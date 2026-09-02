@echo off
chcp 65001 >nul
REM ============================================================
REM  Market Pulse — Git 初始化腳本(TD-04 + TD-13)
REM  用法:將本檔與 .gitignore / .gitattributes / .editorconfig
REM        放入專案根目錄後執行
REM  效果:初始化 git、排除資料檔、統一行尾、建立第一個 commit
REM  安全性:不移動、不修改、不刪除任何既有檔案
REM ============================================================

where git >nul 2>nul
if errorlevel 1 (
    echo [錯誤] 找不到 git,請先安裝:https://git-scm.com/download/win
    pause & exit /b 1
)

if exist .git (
    echo [跳過] 此目錄已是 git repo,不重複初始化。
    pause & exit /b 0
)

if not exist app.py (
    echo [錯誤] 目前目錄找不到 app.py,請在專案根目錄執行本腳本。
    pause & exit /b 1
)

echo [1/5] 初始化 git repo(主分支:main)...
git init -b main >nul

echo [2/5] 檢查資料檔是否會被正確排除...
git check-ignore -q derivatives-platform.sqlite3 2>nul
if errorlevel 1 (
    echo [警告] .gitignore 未生效,請確認 .gitignore 與本腳本在同一目錄。
    pause & exit /b 1
)
echo        OK:derivatives-platform.sqlite3 已排除
git check-ignore -q twse-cache.json && echo        OK:twse-cache.json 已排除

echo [3/5] 加入程式碼與設定檔(資料檔自動排除)...
git add .

echo [4/5] 依 .gitattributes 正規化行尾(CRLF 轉 LF,.bat 除外)...
git add --renormalize .

echo [5/5] 建立初始 commit...
git -c user.name="MarketPulse" -c user.email="local@marketpulse" commit -m "chore: 初始版控;排除執行期資料;統一行尾為 LF(TD-04/TD-13)" >nul

echo.
echo ============================================================
echo  完成!以下是被排除在版控外的執行期資料(檔案仍在原地):
git status --ignored --short | findstr "!!"
echo.
echo  後續建議:
echo    1. git log --stat        檢視初始 commit 內容
echo    2. 資料檔備份改用獨立排程,不再與程式碼混包
echo    3. 未來要把資料移到 data\ 目錄時,設定環境變數:
echo         DERIVATIVES_DB_PATH=data\derivatives-platform.sqlite3
echo         MARKET_PULSE_CACHE_FILE=data\twse-cache.json
echo       (程式已支援,app.py L102-L103,無須改碼)
echo ============================================================
pause
