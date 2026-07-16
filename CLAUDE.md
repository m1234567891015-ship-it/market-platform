# Market Pulse V1.0 R6 — 重構專案

Flask + vanilla JS 台股市場平台。目前進行技術債重構,
工單:見 docs/TD稽核清單.md(源自 MarketPulse_技術債稽核_2026-07-16.xlsx)。

## 指令
- 語法檢查:`python -m py_compile app.py market_config.py derivatives_store.py`
- 單元測試:`python -m unittest test_derivatives_platform.py`
- 冒煙測試:`python e2e_smoke.py`
- 安全檢查:`python security_guardrail_check.py`
- 本地啟動:`python app.py`(http://127.0.0.1:5000)

## 硬性規則
- app.py(15,513 行)與 app.js(34,149 行)只允許局部編輯,
  禁止整檔重寫或整檔重新生成。
- 一次只處理一個 TD 工單項目,完成即 commit,不跨項目連改。
- 禁止讀取或修改 *.sqlite3、twse-cache.json(執行期資料,已由 hook 強制)。
- 重構 = 行為不變。任何函式搬移後,對應測試必須通過才算完成。

## 必須保留的安全不變量(重構時不可退化)
- SQL 一律參數化,禁止任何字串拼接進 execute()
- 前端輸出一律經 escapeHtml()(目前 2,037 處呼叫,單一實作來源)
- CSP 維持 script-src 'self',禁止為方便加入 unsafe-inline
- add_security_headers 與 enforce_api_rate_limit 的行為不可弱化
- SSL 驗證預設開啟;_urlopen_with_ssl_fallback 的 production 阻擋不可移除

## 架構慣例
- 後端拆分目標:routes / fetchers / builders / cache / security 分層
- fetch_* 函式(86 個)收斂方向:宣告式 source registry + 統一 HTTP client
- 資料路徑用環境變數:DERIVATIVES_DB_PATH、MARKET_PULSE_CACHE_FILE(勿寫死)
- Python 縮排 4 空格;JS/CSS/HTML 2 空格;行尾 LF(.bat 除外,見 .gitattributes)
- 台股漲跌顏色慣例:紅漲綠跌(與美股相反),前端修改時注意

## 領域名詞
- 三大法人 = 外資/投信/自營商(institutional investors)
- 籌碼分析 = chip analysis(法人買賣超、融資融券、借券資料)
- TAIFEX = 台灣期交所;TWSE = 證交所;TPEX = 櫃買中心
