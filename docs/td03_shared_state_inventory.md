# TD-03 共享狀態 Inventory（H-05-01／H-05-02）

目前狀態（2026-09-01）：TD-03 部分完成、暫時封存。既有 H-05／H-11 offline contract、canary
與 rollout gate 證據保留；Redis 實連 staging、多 worker rollout 與正式 shared mode 不在封存期間執行。
封存總結見 [`TD03_archive_2026-09-01.md`](TD03_archive_2026-09-01.md)。

日期：2026-08-30

本文件記錄 H-05-01 的現況盤點、雙 process probe 與 H-05-02 shared-state contract。
probe 只 import
`cache.py`、`market_config.py`、`security.py`，不 import `app.py`、不啟動 Flask、
不讀寫正式 SQLite，也不寫 `twse-cache.json`。

## 現況

| 類型 | 名稱 | 模組 | 用途 | 目前邊界 |
|---|---|---|---|---|
| rate limit | `API_RATE_LIMIT_STATE` | `security.py` | client sliding window | process-local；60 秒、120 次、最多 10,000 clients |
| memory cache | `cache_data` | `cache.py` | per-key cache 與 snapshot | process-local；per-key bucket 由 cap 限制 |
| single-flight | `cache_flights` | `cache.py` | generic refresh coalescing | process-local；等待上限 120 秒 |
| short cache | `penny_sector_recommendation_cache` | `cache.py` | penny-sector recommendation | process-local；TTL 30 分鐘 |
| single-flight | `taifex_options_chain_inflight` | `cache.py` | options-chain coalescing | process-local |
| persistent cache | `twse-cache.json` | `cache.py` | cold/warm start snapshot | 由 `MARKET_PULSE_CACHE_FILE` 指定；不是跨 worker lock |
| persistent store | `derivatives-platform.sqlite3` | `derivatives_store.py` | derivatives durable data | 由 `DERIVATIVES_DB_PATH` 指定；H-05-01 不搬移 |

目前部署仍是 `Procfile`/`render.yaml` 的 Gunicorn 1 worker、4 threads。per-key cache
cap 合計 8,800 entries；rate-limit 理論 timestamp slots 為 1,200,000（10,000 × 120），
只是 sizing 上界，不代表實際流量。

## Probe

執行：

```bash
python regression/td03_shared_state_probe.py
```

預期證據：兩個獨立 process 都能接受各自的第一個 rate-limit hit、reader 無法讀到
writer 的 memory cache、兩個 process 都能成為同一 cache-flight key 的 leader。這些
結果確認目前狀態不跨 process 共享；不是缺陷修復，也不是 Redis/SQLite 切換。

## H-05-01 實測結果（2026-08-30）

`python regression/td03_shared_state_probe.py` 輸出 `TD03_SHARED_STATE_PROBE_OK`，觀測值如下：

| 觀測項目 | 結果 |
|---|---|
| writer rate-limit first hit | accepted（`retry_after=null`） |
| reader rate-limit first hit | accepted（`retry_after=null`） |
| writer memory-cache readback | `{"owner":"writer"}` |
| reader memory-cache readback | `null` |
| writer／reader cache-flight leader | 兩者皆為 `true` |
| process-local 判定 | rate limit、memory cache、cache flight 均為 `true` |
| rate-limit 設定 | 60 秒／120 次／10,000 clients；理論 timestamp slots 1,200,000 |
| cache 上限 | 13 buckets／8,800 entries |
| deployment | `Procfile` 與 `render.yaml` 均為 1 worker |

本批次只新增 probe 與 inventory 文件，未引入 Redis、未修改 production runtime、部署設定、正式 SQLite 或 `twse-cache.json`。

## H-05-02 契約實作（2026-08-30）

新增 `shared_state.py`，但尚未由 production request path import。契約固定三類操作：

- `rate_limit_hit`：以 client、時間窗、上限與 client cap 為輸入，回傳 `None` 或 `Retry-After` 秒數；Redis 版本以 Lua 保持滑動窗口與 client eviction 的原子邊界。
- `cache_get`／`cache_set`：以 namespace 與 key 隔離，使用 TTL；payload 必須可 JSON 序列化，memory fake 也以 JSON round-trip 模擬 Redis 的資料邊界。
- `acquire_lease`／`renew_lease`／`release_lease`：以 owner token 驗證持有者，Redis 版本以 `SET NX EX` 與 token-check Lua 防止錯誤釋放他人 lease。

`InMemorySharedStateAdapter` 是 deterministic fake，支援注入 clock 以測試 TTL、窗口到期、stale lease 與 process restart。`RedisSharedStateAdapter` 只接受外部提供的 redis-py-compatible client，不新增 requirements dependency，也不在 H-05-02 接線到 production。
後端 timeout、disconnect 與其他錯誤會轉成明確的 `SharedStateTimeout`、`SharedStateUnavailable` 或 `SharedStateError`；adapter 不靜默 fallback。

契約測試位於 `test_shared_state.py`，涵蓋正常 cache／rate-limit／lease、TTL、owner-token fencing、timeout、disconnect、stale lease 與 memory restart。設定
`MARKET_PULSE_REDIS_URL` 且環境安裝 `redis` 套件時，會額外執行同一組 Redis contract test；未設定時維持可重現的 memory-only 驗證。

## H-05-03 Rate-limit 接線（2026-08-31）

`security.py` 新增 `MARKET_PULSE_RATE_LIMIT_MODE`：

- `local`（預設）：沿用既有 process-local sliding window，不建立 Redis client。
- `shadow`：local 結果仍是實際回應依據，同時送 shared rate-limit 並記錄
  `rate_limit_shadow_compare`；shared timeout／disconnect 只記錄 warning，不改變既有請求行為。
- `redis`：以 `RedisSharedStateAdapter` 的 atomic Lua sliding window 作為權威，使用
  `MARKET_PULSE_REDIS_URL`、namespace 與短 socket timeout；Redis 未設定、缺少 optional
  package、timeout 或 disconnect 時，受保護 API 回 503
  `RATE_LIMIT_BACKEND_UNAVAILABLE`（fail-closed），`/api/health` 仍 exempt。

shared adapter 採 lazy initialization 與首次 `ping`，不會在 `local` 模式產生外部連線。
H-05-03 未修改 Procfile、render.yaml、requirements、worker 數、SQLite、`twse-cache.json`
或 baseline；實連 Redis contract test 只有在 `MARKET_PULSE_REDIS_URL` 配置時才執行。

## H-05-04 Single-flight lease 接線（2026-08-31）

`cache.py` 新增 `CacheFlightHandle` 與 shared lease mode，設定
`MARKET_PULSE_SINGLE_FLIGHT_MODE=redis` 才會啟用；預設 `local` 仍使用既有
process-local event。generic cache-flight 與 TAIFEX options chain 各自保留原本的
local registry，並共用 H-05-02 adapter 的 lease contract。

- leader 以 process／thread／timestamp 組成 owner token，取得 `cache-flight:*` 或
  `options-flight:*` lease；lease TTL 與等待上限均為 120 秒。
- follower 在 shared mode 輪詢 lease 是否仍 active，等待到期即回傳未完成；options chain
  也統一傳入 120 秒上限。leader finish 只以相同 owner token release，舊 leader 的 stale
  release 不會刪除新 leader 的 lease。
- shared claim／wait／release 發生 timeout 或 disconnect 時，明確記錄 warning；claim 會
  降級為 local leader，follower wait 會結束並交由既有呼叫端重新檢查 cache／必要時重抓，
  不留下永久等待或永久 lock。

H-05-04 只接線 feature flag，未啟用 shared mode，也未修改 Procfile、render.yaml、worker
數、requirements、SQLite、`twse-cache.json` 或 baseline。驗證由
`test_cache_shared_state.py` 覆蓋 local event、cross-process lease wait、stale owner
fencing、backend failure fallback 與 options chain lease。

## H-05-05 Cache L2 接線（2026-08-31）

`cache.py` 新增 `MARKET_PULSE_CACHE_L2_MODE=local|redis`，預設 `local`；只有既有
`read_memory_cache`／`write_memory_cache` 共用路徑且 payload 可 JSON 序列化的下列 6 個
bucket 先納入 allowlist：

`live_search_dedup`、`us_options_chains`、`global_market_items`、
`yahoo_tw_future_technical_candles`、`taifex_openapi_list`、
`yahoo_tw_stock_resources`。

- read path 先查 bounded local L1；L1 miss 才查 Redis L2，命中後回填 L1 並再次套用 bucket cap。
- write path 保留 L1 寫入，同時以呼叫端傳入的實際 TTL 寫入 Redis L2；namespace 包含
  `CACHE_VERSION`（目前為 `cache-v13`），避免版本不相容資料互讀。
- `external_text` 刻意排除，因同一 bucket 同時承載文字與 binary payload；不以失敗序列化
  迫使既有外部資料流程改變。未經 accessor 的 snapshot／direct `cache_data` 也留待後續批次。
- L2 miss、Redis timeout／disconnect 或非 JSON payload 只記錄 debug 並回到既有 local
  miss／local write，不阻斷資料抓取；disk `twse-cache.json` 仍只作 warm-start。

H-05-05 未啟用 Redis L2、未修改 Procfile、render.yaml、worker 數、requirements、SQLite、
`twse-cache.json` 或 baseline；`test_cache_shared_state.py` 覆蓋 local default、L2
write/read-back、version namespace、failure fallback 與 binary bucket exclusion。

## H-05-06 Background scheduler lease（2026-08-31）

`cache.py` 新增 `MARKET_PULSE_BACKGROUND_LEASE_MODE=local|redis`；預設 `local` 維持既有
background updater。shared mode 下每個 process 的 updater 必須先取得
`background-updater` lease，只有 owner 才執行 TPEx 與 TWSE 兩段 refresh。

- lease TTL 為 120 秒，refresh 期間由 daemon renew thread 續租；finally 以 owner token
  release，stale owner 不可釋放新 owner 的 lease。
- lease 被其他 worker 持有時 skip 該輪；lease 過期可由下一個 worker 接管。Redis
  timeout／disconnect／未設定時同樣 skip 該輪，不 fallback 成 local refresh，避免多 worker
  同時更新；下一輪再嘗試，避免永久 lock。
- `run_background_update_cycle()` 抽出單輪流程，供 loop 與測試共用；未啟用 shared mode
  時不建立 Redis client。H-05-06 未修改 Procfile、render.yaml、worker 數、requirements、
  SQLite、`twse-cache.json` 或 baseline。

`test_cache_shared_state.py` 覆蓋 local default、另一 worker 持有時 skip、正常 release、
續租、expired lease takeover 與 backend failure skip。

## H-05-07 Staging/canary preflight（2026-08-31）

新增 `regression/td03_shared_state_canary.py`，以兩個 worker facade 共用
`InMemorySharedStateAdapter` 執行可重現的 offline canary；腳本不 import `app.py`、不啟動
Flask、不讀寫正式 SQLite，也不寫 `twse-cache.json`。preflight 通過項目包括：

- `Procfile` 與 `render.yaml` 的 deployment gate 均維持 `--workers 1`。
- shared rate-limit 的跨 worker retry-after、cache L1 以外的共享 readback、cache-flight lease
  contention／owner-token fencing／expired takeover。
- `background-updater` 單 owner、過期接管，以及 rate-limit、cache、lease backend fault injection
  均回報明確 `SharedStateUnavailable`，不靜默建立 local lock。

本環境未配置 `MARKET_PULSE_REDIS_URL`，因此未開啟實連 Redis staging canary；offline preflight
不宣稱 Redis server 已驗證。`Procfile`、`render.yaml`、worker 數、SQLite、`twse-cache.json`
與 baseline 均未修改；`requirements.txt` 已加入經測試的 `redis==8.1.0`，但尚未啟用 Redis mode。
實連 Redis、provider、未納入 bucket 與 multi-worker
rollout 仍待 staging 環境配置後另批次處理。

## H-05 未完成事項盤點（2026-08-31）

本次授權後重新檢查結果如下：

- 實連 Redis staging canary：Redis client dependency 已安裝並固定為 `redis==8.1.0`；仍待配置
  `MARKET_PULSE_REDIS_URL` 與 staging Redis service，本機目前兩者不可用，不能以 offline fake
  取代實連驗證。
- Cache L2 未納入的 7 個 bucket：`external_text`、`global_markets`、`sector_charts`、
  `stock_details`、`taifex_options_chain`、`us_etf_center`、`yahoo_tw_option_chain`。
  `external_text` 含 binary payload，其他 bucket 仍須逐一完成 JSON-safe／TTL／行為回歸評估，
  不在本次沒有 staging backend 的情況下直接切換。
- provider 與 multi-worker rollout：尚未執行；`Procfile`、`render.yaml` 仍固定 1 worker，
  需先取得雙 worker 壓測、Redis latency／unavailable 與 lease takeover 數據，再另批次提出
  deployment／requirements 變更與回退方案。

## 封存事項（暫不處理）

使用者決定暫緩 H-05 的實連 Redis staging、`MARKET_PULSE_REDIS_URL` 配置、未納入 L2 bucket
擴充、provider 評估與 multi-worker rollout。後續重新授權且 staging 條件具備時，再以獨立批次
恢復；在此之前維持 `redis==8.1.0` client dependency、所有 shared mode 預設關閉與單 worker
部署護欄。

## H-05 目前完成度（2026-08-31）

H-05-01～H-05-06 為完整完成，H-05-07 已完成 offline canary 與 dependency test；以 7 個
正式批次計算，完整完成度為 6/7（約 85.7%），H-05-07 的實連 staging 部分因外部條件封存。
目前授權範圍已完成，H-05 不標示為 100%。

## 後續前置輸入

- 以 probe 輸出的兩 process elapsed time、active key 數與現有 cap 作為後續容量量測起點。
- H-05-07 完成後仍維持 `--workers 1`，已補齊 `redis==8.1.0` client dependency 但不啟用 Redis mode、不修改部署設定；實連 staging、provider、未納入 bucket 與 multi-worker rollout 仍須另批次確認。

## H-11-01 Redis staging 決策與 preflight（2026-08-31）

H-11-01 已完成 provider／成本／資料區域／secret 管理決策與 offline preflight，實連部分
仍為待辦：`MARKET_PULSE_REDIS_URL` 與 `REDIS_URL` 均未設定，本機沒有 Redis staging
service，因此沒有執行或宣稱 `PING`／sentinel／Redis contract 實連通過。

- 首選 provider 為與 Render web service 同 workspace／同 region 的 Render Key Value；
  `render.yaml` 未宣告 region，必須由 dashboard 確認後才可 provisioning，不猜測、不在
  本批改 deployment。Upstash 只列為 Render 不可用時的隔離 benchmark 備選。
- 已定義最小 256 MB staging plan 的成本核對 gate、secret 只由 environment／secret store
  注入、staging／production instance／credential／namespace 隔離，以及 provider snapshot／
  RDB、故障前 checkpoint、隔離 restore 的 backup runbook。未建立付費資源、未執行 backup。
- 已對齊既有 implementation：shared client connect／socket timeout 預設 1 秒；rate-limit
  Redis mode fail-closed；cache L2／single-flight／background lease 分別依既有 local
  miss、local recheck、skip round policy 降級；health 必須包含 PING、短 TTL sentinel 與
  Redis contract，不能只驗 PING。
- 後續 gate 為 URL present（不洩漏 secret）、同 region／namespace、backup restore、
  p50／p95／p99 latency、timeout／disconnect fault injection 全部有證據；在此之前所有
  shared modes 維持 `local`、`Procfile`／`render.yaml` 維持 `--workers 1`。

詳見 [`TD03_H11-01_redis_staging_decision_2026-08-31.md`](TD03_H11-01_redis_staging_decision_2026-08-31.md)。

驗證紀錄：`td03_shared_state_canary.py` 為 `TD03_SHARED_STATE_CANARY_OFFLINE_OK`；
`redis==8.1.0` import、syntax、diff check 通過；shared-state／cache／TD-03 canary／
derivatives unit 共 200 tests PASS、1 skip（無 Redis URL）；security 16/16 PASS；
`E2E_SMOKE_OK`；`verify_against_baseline.py --full` 已執行，外部網路阻擋依規範標為
`[外部問題]`，未更新 baseline。

## H-11-02 L2 bucket 導入（2026-08-31）

H-11-02 已完成 7 個候選 bucket 的逐一盤點與最小 runtime 接線。6 個 JSON-safe bucket
已加入 `cache.py` 的 `CACHE_L2_BUCKETS`，並把原本直接操作 process-local dict 的路徑改為
共用 `read_memory_cache`／`write_memory_cache`：`global_markets`、`sector_charts`、
`stock_details`、`taifex_options_chain`、`us_etf_center`、`yahoo_tw_option_chain`。

- `stock_details` 補入中央 `stock_detail` TTL（5 分鐘）；其餘沿用既有 accessor／registry
  TTL：global／sector／ETF 5 分鐘、TAIFEX／Yahoo option 1 分鐘。所有 L2 write 均經既有
  JSON round-trip boundary，L1 miss 會 promotion 回填並重新套用 bucket cap。
- `external_text` 維持排除：同一 bucket 的文字 accessor 也服務 `fetch_binary`，bytes
  無法通過 JSON boundary；測試明確確認 Redis mode 下不會呼叫 L2 adapter，保留原本 local
  binary cache 行為。這是本批對第 7 個候選的保守結論，不是遺漏。
- `test_cache_shared_state.py` 新增 6 bucket 的 JSON round-trip、TTL expiry、L1 promotion
  與 disconnect fallback contract；完整 shared-state／cache／TD-03 canary／derivatives
  unit 為 202 tests PASS、1 skip（Redis URL absent）。
- 本機仍沒有 `MARKET_PULSE_REDIS_URL`，所以本批驗證的是 offline／in-memory contract，
  不宣稱 Redis server 實連；H-11-03 雙 worker staging 壓測仍待 staging URL 與服務。

詳見 H-11-01 決策文件與本批 modified files：`cache.py`、`market_config.py`、
`routes_twse.py`、`routes_global_market.py`、`fetchers.py`、`test_cache_shared_state.py`。

## H-11-03 雙 worker load／fault-injection canary（2026-08-31）

新增 `regression/td03_h11_03_canary.py` 與 `test_td03_h11_03_canary.py`。canary 僅使用
`InMemorySharedStateAdapter` 與隔離 Flask request context，不 import production `app.py`、
不開 Redis connection、不讀寫正式 SQLite／`twse-cache.json`。

- 雙 worker concurrent load：100 requests（每 worker 50），共享 rate-limit window 結果
  50 accepted／50 rejected；6 個 H-11-02 L2 bucket 均完成 cross-worker JSON readback。
- `cache-flight`、`options-flight`、`background-updater` 均驗證 single-owner、release／
  takeover；另驗證 options lease expired takeover 與 owner-token fencing，stale owner 不可
  釋放新 owner。
- fault injection：rate-limit 為 `503 RATE_LIMIT_BACKEND_UNAVAILABLE` fail-closed；cache
  L2 與 generic／options single-flight 回 local fallback；background updater skip 該輪，
  不偷偷建立多 worker refresh。
- `MARKET_PULSE_REDIS_URL` 仍 absent，報告的 real Redis canary 為 `not-run`；因此 H-11-03
  的實 staging load／latency／disconnect 壓測仍待 URL、provider instance 與 region gate。

驗證：`TD03_H11_03_CANARY_OFFLINE_OK`；205 tests PASS、1 skip（Redis URL absent）；security
16/16、`E2E_SMOKE_OK` 與 `verify_against_baseline.py --full` 均已執行，外部網路錯誤依規範
標記為 `[外部問題]`。未修改 baseline、CSP、部署設定、worker、SQLite 或 `twse-cache.json`。

## H-11-04 rollout gate 與 rollback（2026-08-31）

新增唯讀 `regression/td03_h11_04_rollout_gate.py` 與其測試。gate 輸出
`TD03_H11_04_ROLLOUT_GATE_BLOCKED`、`eligible=false`：safe state 通過（shared modes 全為
`local`、`Procfile`／`render.yaml` 均為 1 worker、入口為 `app:app`），但 Redis URL、實連
health、backup／restore、實 staging dual-worker evidence、observation period 與 manual
rollout approval 均未滿足。

本批完成 rollout entry gate 與 rollback runbook，未 provisioning、未切換 shared modes、未
增加 worker、未修改 `Procfile`／`render.yaml`。未來若所有 gate 通過，仍須另立部署變更批次；
rollback 順序固定為關閉 shared modes → 恢復單 worker → 回退單一 adapter／deployment commit。

驗證：gate tests 2/2 PASS；完整 shared-state／cache／canary／derivatives unit 207 tests
PASS、1 skip（Redis URL absent）；security 16/16、`E2E_SMOKE_OK`、full verify 均已執行，
外部網路錯誤標記 `[外部問題]`，未更新 baseline。

詳見 [`TD03_H11-04_rollout_gate_2026-08-31.md`](TD03_H11-04_rollout_gate_2026-08-31.md)。

## H-11 Redis 實連與多 worker rollout 封存（2026-08-31）

依授權暫不處理尚未完成的 Redis 實連與多 worker staging rollout，另立封存文件
[`TD03_H11_redis_rollout_deferred_2026-08-31.md`](TD03_H11_redis_rollout_deferred_2026-08-31.md)。
目前 `MARKET_PULSE_REDIS_URL` 未注入，Redis health、backup／restore、real bucket
contract、real dual-worker staging evidence、觀測期與人工 rollout approval 均未完成；
rollout eligibility 維持 `eligible=false`。

封存期間維持 safe state：shared modes 為 `local`，`Procfile`／`render.yaml` 為單 worker；
不 provisioning、不切換 shared modes、不增加 worker、不發佈。解封須重新授權，並先具備
隔離 staging URL、provider／region／namespace、backup／restore、完整 staging evidence、
觀測期與人工核准。
