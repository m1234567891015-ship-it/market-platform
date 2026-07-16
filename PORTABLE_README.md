# Market Pulse 可攜使用說明

## 在本機或另一台 Windows 電腦啟動

1. 將整個 `test` 資料夾複製到目標電腦。
2. 開啟資料夾並雙擊 `START_WEBSITE.bat`。
3. 批次檔會自動尋找可用 port。預設使用 `http://127.0.0.1:5000/`；若 5000 已被占用，會自動改用下一個可用 port，並在視窗中顯示實際網址。
4. 保持啟動視窗開著；要停止網站時在該視窗按 `Ctrl+C`。

## 執行環境

- 若資料夾內有 `python_runtime\python.exe`，啟動檔會優先使用它。
- 若沒有內附 Python runtime，目標電腦需安裝 Python 3.11 以上，並可使用 `py` 或 `python` 指令。
- 第一次啟動時若缺少 Flask/certifi，啟動檔會依 `requirements.txt` 自動安裝；這一步需要網路。

## 線上資料

- TWSE、TPEx、TAIFEX、Yahoo Finance 等線上資料需要目標電腦可連外網。
- 若外部資料來源短暫無法連線，網站仍可用內附的 `twse-cache.json` 顯示快取資料。

## 驗證

在資料夾內可執行：

```powershell
python portable_check.py
python live_source_validation.py
```

`portable_check.py` 會確認頁面、資產、health API、股票查詢 API 與本機連結可用。  
`live_source_validation.py` 會實際連線驗證 TWSE 與 TAIFEX 線上資料導入。
