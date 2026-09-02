# TD-19 Required-key 欄位政策盤點

本文件為 H-07-01 產出，盤點 `regression/baseline/manifest.json` 的 44 個 API endpoint，供後續 H-07-02 確認 allowlist schema 使用。表內欄位是「候選政策」，尚未直接啟用為 verifier 規則。

## 判定語意

- `R`（required）：回應為預期成功型態時，key 必須存在；value 可以是 `null`、空陣列或合法空資料，除非備註另有說明。
- `O`（optional）：依資料源、交易日、查詢條件或功能分支可能不存在；缺少不應報 schema failure。
- `E`（error-only／待補 fixture）：現有 baseline 只捕捉錯誤或失敗形態，先不宣告成功回應的 required key。
- 本批只盤點 key 的「存在性」，不把非空、數值範圍、日期新鮮度或資料筆數當成 required-key 規則；那些屬其他契約或資料品質檢查。

## Endpoint matrix

| # | Manifest name | Request path | Baseline 型態 | 候選 required keys（R） | 可為 null／空資料或暫不要求 | 政策理由／備註 |
|---:|---|---|---|---|---|---|
| 1 | `api__health` | `/api/health` | value | `status` | `lastError` 可為 null | 健康檢查的最小成功訊號。 |
| 2 | `api__twse__site-data` | `/api/twse/site-data` | structure | `snapshotDate`, `stockCount`, `sectors` | `sectors` 可為空；其餘時變欄位暫不要求 | 首頁共用資料 envelope；日期、股票數與板塊容器是穩定入口。 |
| 3 | `api__twse__live-sectors` | `/api/twse/live-sectors` | structure/live | `snapshotDate`, `sectors` | `sectors` 可為空 | 即時板塊資料的日期與板塊容器。 |
| 4 | `api__twse__live-overview` | `/api/twse/live-overview` | structure/live | `snapshotDate`, `marketOverview`, `marketStats`, `stocks` | `stocks` 可為空 | 即時大盤頁面依賴 overview、stats 與 stocks 三個容器。 |
| 5 | `api__twse__live-stocks` | `/api/twse/live-stocks` | structure/live | `snapshotDate`, `count`, `stocks` | `stocks` 可為空、`count` 可為 0 | 股票清單的查詢結果 envelope。 |
| 6 | `api__twse__live-search` | `/api/twse/live-search` | structure/live | `query`, `count`, `results` | `results` 可為空 | 搜尋輸入與結果容器是穩定契約；source／日期屬 metadata。 |
| 7 | `api__yahoo__sector` | `/api/yahoo/sector` | structure | — | 現有 fixture 僅有 `error` | 先補成功 fixture，再決定成功型 required keys；錯誤回應不能冒充成功契約。 |
| 8 | `api__yahoo__sector-chart` | `/api/yahoo/sector-chart` | structure | — | 現有 fixture 僅有 `error` | 同上；目前不以 `error` 作成功欄位。 |
| 9 | `api__market__penny-sector-recommendations` | `/api/market/penny-sector-recommendations` | structure | `available`, `markets` | `markets` 可為空 | 功能是否可用與市場結果容器是穩定入口；sourceNote／updatedAt 為 metadata。 |
| 10 | `api__market__international-indexes` | `/api/market/international-indexes` | structure | `count`, `indexes` | `indexes` 可為空、`count` 可為 0 | 國際指數清單 envelope。 |
| 11 | `api__global-market__us-stocks` | `/api/global-market/us-stocks` | structure | `category`, `items`, `summary` | `items`、`summary` 可為空 | 全球市場共用 category／items／summary contract。 |
| 12 | `api__global-market__futures` | `/api/global-market/futures` | structure | `category`, `items`, `summary` | `items`、`summary` 可為空 | 與同系列頁面一致；v1 metadata 不列為最低必要欄位。 |
| 13 | `api__global-market__options` | `/api/global-market/options` | structure | `category`, `items`, `summary` | `items`、`summary` 可為空 | 選擇權全球市場頁面最低入口。 |
| 14 | `api__global-market__precious-metals` | `/api/global-market/precious-metals` | structure | `category`, `items`, `summary` | `items`、`summary` 可為空 | 貴金屬全球市場頁面最低入口。 |
| 15 | `api__global-market__bonds` | `/api/global-market/bonds` | structure | `category`, `items`, `summary` | `items`、`summary` 可為空 | 債券全球市場頁面最低入口。 |
| 16 | `api__index` | `/api/index` | structure | `data`, `success` | `data` 可為空或 null，依既有 envelope | 台指資料 API 的共用成功 envelope。 |
| 17 | `api__derivatives__v1-status` | `/api/derivatives/v1-status` | value | `data`, `success` | `data` 內容依狀態而變 | 先守住 v1 status envelope；value compare 仍由既有 baseline 負責。 |
| 18 | `api__futures` | `/api/futures?sort=open_interest` | structure | `data`, `success` | `data` 可為空 | 期貨清單共用 envelope。 |
| 19 | `api__futures__TX` | `/api/futures/TX` | structure | `data`, `success` | `data` 可為空 | 單一期貨商品共用 envelope。 |
| 20 | `api__futures__TX__candles` | `/api/futures/TX/candles` | structure | `data`, `success` | `data` 可為空 | K 線資料受日期與資料源影響，先只要求 envelope。 |
| 21 | `api__options` | `/api/options?underlying=TXO` | structure | `data`, `success` | `data` 可為空 | 選擇權清單共用 envelope。 |
| 22 | `api__open-interest` | `/api/open-interest?symbol=TX` | structure | `data`, `success` | `data` 可為空 | 未平倉量資料共用 envelope。 |
| 23 | `api__institution` | `/api/institution` | structure | `data`, `success` | `data` 可為空 | 法人資料可能因交易日無資料，key 仍需存在。 |
| 24 | `api__basis` | `/api/basis` | structure | `data`, `success` | `data` 可為空 | 基差資料共用 envelope。 |
| 25 | `api__news` | `/api/news` | structure | `data`, `success` | `data` 可為空 | 新聞資料共用 envelope。 |
| 26 | `api__ai-analysis` | `/api/ai-analysis?target=TXO` | structure | `data`, `success` | `data` 可為空 | AI 分析可能沒有內容，但成功 envelope 不應消失。 |
| 27 | `api__futures__TX__technical-candles` | `/api/futures/TX/technical-candles` | structure | `data`, `success` | `data` 可為空 | 技術 K 線資料共用 envelope。 |
| 28 | `api__options__chain` | `/api/options/chain?underlying=TXO` | structure | `data`, `success` | `data` 可為空 | 選擇權鏈資料共用 envelope。 |
| 29 | `api__pcr` | `/api/pcr?underlying=TXO` | structure | `data`, `success` | `data` 可為空 | PCR 資料共用 envelope。 |
| 30 | `api__maxpain` | `/api/maxpain?underlying=TXO` | structure | `data`, `success` | `data` 可為空 | Max pain 資料共用 envelope。 |
| 31 | `api__us-market__etf-center` | `/api/us-market/etf-center` | structure | `category`, `items`, `summary` | `items`、`summary` 可為空；error 依成功／失敗分類 | ETF center 與全球市場頁面共享主要容器。 |
| 32 | `api__us-market__search` | `/api/us-market/search?q=AAPL` | structure | `query`, `count`, `results` | `results` 可為空 | 搜尋頁穩定 envelope。 |
| 33 | `api__us-market__listed` | `/api/us-market/listed` | structure | `count`, `results` | `results` 可為空、`count` 可為 0 | 上市清單結果 envelope。 |
| 34 | `api__us-market__nyse-listed` | `/api/us-market/nyse-listed` | structure | `group`, `results`, `returned` | `results` 可為空、`returned` 可為 0 | NYSE 清單的分組與結果容器；query／error 屬分支 metadata。 |
| 35 | `api__us-market__options-chain__AAPL` | `/api/us-market/options-chain/AAPL` | structure | `symbol`, `calls`, `puts`, `summary` | `calls`、`puts`、`summary` 可為空 | 選擇權鏈 UI 的最低穩定容器；鎖定／fallback 欄位另依分支檢查。 |
| 36 | `api__us-market__symbol__AAPL` | `/api/us-market/symbol/AAPL` | structure | `symbol`, `name`, `market`, `source` | `name` 或資料分支欄位可為 null | 個股詳情最低識別欄位；報價、歷史、新聞等依資料可用性變動。 |
| 37 | `api__us-market__sector-stocks` | `/api/us-market/sector-stocks` | structure | `sector`, `items`, `usable` | `items` 可為空、`usable` 可為 false | sector stocks 頁面需要 sector、items 與可用性訊號。 |
| 38 | `api__twse__all-stocks` | `/api/twse/all-stocks` | structure | `snapshotDate`, `count`, `stocks` | `stocks` 可為空、`count` 可為 0 | 台股清單 envelope。 |
| 39 | `api__twse__etfs` | `/api/twse/etfs` | structure | `count`, `items` | `items` 可為空、`count` 可為 0 | ETF 查詢結果最低容器；分類、排序與 summary 屬選項／metadata。 |
| 40 | `api__twse__search` | `/api/twse/search?q=2330` | structure | `query`, `count`, `results` | `results` 可為空、`count` 可為 0 | 搜尋 UI 的穩定 envelope。 |
| 41 | `api__twse__stock__2330` | `/api/twse/stock/2330` | structure | `code`, `name`, `close`, `historyDays` | `close` 可為 null、`historyDays` 可為 0 | 個股詳情的識別、報價與歷史可用性欄位；各資料模組可空。 |
| 42 | `api__twse__stock__0050` | `/api/twse/stock/0050` | structure | `code`, `name`, `close`, `historyDays` | `close` 可為 null、`historyDays` 可為 0 | 與 2330 同一 response contract，避免只保護單一 symbol。 |
| 43 | `api__twse__stock__2330__shareholders` | `/api/twse/stock/2330/shareholders` | structure | `code`, `shareholderDistribution` | `shareholderDistribution` 可為空或 unavailable | 股東分布資料的識別與資料容器。 |
| 44 | `api__twse__stock__2330__institutional-history` | `/api/twse/stock/2330/institutional-history` | structure | `code`, `institutionalTrades`, `institutionalTradeHistory` | 兩個 history 容器可為空 | 法人歷史頁面需同時保留摘要與歷史容器；日期／market metadata 不列最低必要欄位。 |

## H-07-02 待確認事項

1. 是否採用本表候選欄位，或由各 endpoint owner 調整 required／not-required 政策。
2. `dot-path` 是否在第一版支援巢狀 object；第一版不應以陣列 index 作 required path。
3. `null`／空陣列只代表 key 存在，不代表資料品質通過；非空驗證不得混入 TD-19。
4. 第 7、8 個 Yahoo endpoint 需先補成功 fixture，否則只能驗證 error classification，不能宣告成功 schema 完整。
5. 目前工作樹既有的 `REQUIRED_KEY_PATHS` 草稿只涵蓋部分 endpoint；H-07-02 必須先決定是否擴充到本表 44/44 的明確政策，再進入 verifier 實作。

## H-07-01 驗證結果

- matrix row count：`44`
- `python -m py_compile app.py regression/verify_against_baseline.py`：PASS
- `python -m unittest test_derivatives_platform.py regression/test_offline_verifier.py`：177 tests PASS
- `python regression/verify_against_baseline.py --quick`：`VERIFY_OK`
- `python security_guardrail_check.py`：16/16 PASS
- `python e2e_smoke.py`：`E2E_SMOKE_OK`
- `python regression/verify_against_baseline.py --full`：允許外部連線重跑為 `VERIFY_OK`，21 頁 frontend、94 條 interaction、cached/live API 與 security 全部 PASS
- 本批只新增 matrix 文件；未更新 golden baseline，未修改產品 API、CSP、部署設定或既有 TD-19 verifier 草稿。
