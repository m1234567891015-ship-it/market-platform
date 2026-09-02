# TD-03 H-11-01 Redis staging 決策與 preflight

日期：2026-08-31  
範圍：只處理 provider／成本／延遲／資料區域／secret 管理決策，以及 staging
backup、health、timeout、fail-closed／降級的驗收條件。  
狀態：🟡 決策與 offline preflight 完成；實連等待 staging URL 與服務；TD-03 整體已於 2026-09-01 暫時封存。

## 1. 本批邊界與現況

- `MARKET_PULSE_REDIS_URL` 與 `REDIS_URL` 均未設定；本機沒有可用的 Redis staging
  service，因此本批不執行外部 `PING`、不宣稱 Redis server 實連通過。
- `redis==8.1.0` 已在 requirements 中；既有 `regression/td03_shared_state_canary.py`
  可在不 import app、不啟動 Flask、不讀寫正式 SQLite／`twse-cache.json` 的條件下驗證
  cross-worker contract。
- `render.yaml` 與 `Procfile` 仍固定 Gunicorn `--workers 1`；本批不修改 deployment、
  worker、baseline、CSP 或正式資料。
- shared namespace 預設為 `market-pulse:v1`，cache L2 另外包含 `cache-v13`。未來 staging
  必須用獨立 namespace（例如 `market-pulse:staging:h11-01`），不可與 production key
  混用；這是 staging provisioning 的輸入，不在本批寫入環境設定。

## 2. Provider／成本／區域決策

### 首選：Render Key Value

應用目前以 Render web service 部署，故首選同一 Render workspace／region 的 Key Value：

1. 先從 Render web service dashboard 取得實際 region；`render.yaml` 沒有 region 欄位，
   **不得猜測 region，也不得在本批補寫 region**。
2. Key Value 與 web service 必須同 region，優先使用 internal URL；外部 access 維持關閉，
   只有必要的 staging 故障測試才短暫開放並套用 IP allowlist／TLS。
3. 先選最小可用的 256 MB staging plan，執行前由服務擁有人在 Render dashboard 核對
   當期月費、disk／persistence 與 region 可用性；費用不寫死在 repo，也不在本批建立
   付費資源。參考：[Render Key Value](https://render.com/docs/key-value)、
   [Render compute plans](https://render.com/docs/compute-plans)。

### 備選：Upstash Redis

只有 Render region 不可用或無法提供隔離 staging 時，才評估 Upstash。它可作為短期
benchmark／故障注入環境，但需以 `rediss://`、TLS、IP／帳號控管和明確 region 進行，
並將公網 latency／egress 納入測量，不視為 production rollout 的預設 backend。

截至本批查核的官方公開價目，Upstash 有 Free $0（含 256 MB、每月 500K commands）、
PAYG $0.20／100K commands，以及固定 250 MB $10／月；實際採用前仍須重新核對帳單與
region 價格：[Upstash Redis pricing](https://upstash.com/pricing/redis)。region 必須選
與應用相同或網路距離最近者；可用 region 以 [Upstash FAQ](https://upstash.com/docs/redis/help/faq)
為準，不以「台灣」這個使用者市場名稱代替 cloud region。

## 3. Secret、backup 與資料界線

- 唯一 application secret input 為 `MARKET_PULSE_REDIS_URL`；由 staging provider 的
  secret／environment-variable store 注入，禁止進 Git、`render.yaml`、shell history、
  log、測試輸出、screenshot 或驗證 artifact。檢查時只輸出 absent／present，不輸出 URL。
- production 與 staging 必須使用不同 instance、不同 credential、不同 namespace；禁止
  用正式 URL 做測試。credential rotation 後先 health check，再撤銷舊 credential。
- Redis shared state 只保存 rate-limit、cache L2、single-flight 與 updater lease，
  不是 SQLite／`twse-cache.json` 的 source of truth。正式資料不備份到 Redis，也不因本批
  而讀寫正式資料檔。
- staging provisioning 前建立 provider-native snapshot／RDB backup；故障注入前另做
  checkpoint，restore 到隔離 staging instance 後核對 key count、TTL、namespace 與
  credential isolation。H-11-01 只有 backup／restore runbook 與驗收條件，因沒有 URL／服務
  不執行實際 backup 或 restore。

## 4. Health、timeout 與 failure policy

### Health check

實連條件具備後，先以同一 `MARKET_PULSE_REDIS_URL` 做：

1. `PING`；
2. 以 staging namespace 寫入隨機 sentinel、短 TTL read-back，再刪除 sentinel；
3. 執行 `test_shared_state.py` 的 Redis contract，確認 TTL、sliding-window、owner-token
   fencing、lease takeover、timeout 與 disconnect 行為。

sentinel 不得使用 production key，不得留下永久 key。`/api/health` 維持 rate-limit exempt，
但 shared backend 不健康時不可把健康狀態誤報為 Redis ready。

### Timeout 與降級

- 三個 Redis client path 的 connect／socket timeout 由
  `MARKET_PULSE_SHARED_STATE_TIMEOUT_SECONDS` 控制，預設為 1 秒且不低於 0.1 秒；rate-limit
  與 cache adapter 建立時先 `PING`，不做無限等待。
- `MARKET_PULSE_RATE_LIMIT_MODE=redis`：Redis missing／timeout／disconnect 回
  `503 RATE_LIMIT_BACKEND_UNAVAILABLE`，維持 fail-closed；不可靜默切回 local rate limit。
- `MARKET_PULSE_CACHE_L2_MODE=redis`：L2 失敗只回既有 local miss／local write；L1 與資料
  抓取行為維持可用。
- `MARKET_PULSE_SINGLE_FLIGHT_MODE=redis`：claim／wait 失敗結束 shared wait，交回既有
  local path／cache recheck，不留下永久 lock。
- `MARKET_PULSE_BACKGROUND_LEASE_MODE=redis`：backend 不可用或 lease 失敗時 skip 該輪，
  不降級為多 worker 同時 refresh；下一輪再嘗試。
- 所有 lease 維持 TTL、renew 與 owner-token fencing；timeout／disconnect fault injection
  必須證明上述 policy，而不是只證明 `PING` 成功。

## 5. H-11-01 通過門檻與後續 gate

只有下列證據齊全才可將此批的「實連」標為完成，並進入 H-11-02：

- staging URL 已由 secret store 注入，驗證輸出不含 secret；provider instance、region、
  plan／成本上限與 staging namespace 已記錄。
- `PING`、sentinel TTL read-back、backup／restore 及 Redis contract 全部通過。
- 記錄 Redis 與 application 的 p50／p95／p99 latency、timeout count、disconnect recovery；
  任一 p95 接近 1 秒 shared timeout 或出現未解釋 error，停止 rollout 並回到 shared modes
  off。
- H-11-02 的 7 個 L2 bucket 已完成 offline 驗證；其中 `external_text` 因同時承載 binary
  payload 仍排除，不能以 JSON boundary 安全納入。H-11-03 才能做 dual-worker load／fault
  injection。
- 在 H-11-04 人工 rollout 核准前，所有 shared modes 保持預設 `local`、deployment 保持
  `--workers 1`。

## 本批結論

provider 首選、成本與 region gate、secret／backup runbook、health／timeout／failure policy
均已定義；本機 preflight 確認沒有 Redis URL，因此實連與任何 staging provisioning 明確
延後。未修改 baseline、CSP、部署設定、worker、SQLite 或 `twse-cache.json`。

## 驗證紀錄

- `python regression/td03_shared_state_canary.py`：`TD03_SHARED_STATE_CANARY_OFFLINE_OK`；
  deployment gate、cross-worker shared contract、fencing／takeover 與 fault policy 全部 pass，
  real Redis 為 `not-run`（URL absent）。
- `redis==8.1.0` import、Python syntax 與 `git diff --check` 通過；本批沒有 JS 變更，無需
  另做 Node syntax check。
- `python -m unittest test_shared_state.py test_cache_shared_state.py
  test_td03_shared_state_canary.py test_derivatives_platform.py`：200 tests PASS、1 skip；
  skip 原因為沒有 `MARKET_PULSE_REDIS_URL`。
- `security_guardrail_check.py`：16/16 PASS；`e2e_smoke.py`：`E2E_SMOKE_OK`。
- `python regression/verify_against_baseline.py --full` 已執行；受限環境的外部資料／瀏覽器
  網路阻擋依既有規範歸類為 `[外部問題]`，沒有以更新 baseline 消除差異，也沒有發現本批
  文件變更需要修改 API／frontend baseline 的理由。
