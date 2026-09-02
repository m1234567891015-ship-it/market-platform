# TD-03 本機 Redis staging 實連證據（2026-09-01）

## 狀態

本次已依明確授權啟動 workspace 隔離的本機 Redis service，完成 real Redis
health、contract、雙 process consistency 與 disconnect fault probe；TD-03
仍未解封為 production rollout。`Procfile`／`render.yaml` 未修改，shared modes
仍維持 `local`，入口仍為 `app:app`。

## 最新逐項進度（2026-09-01）

| 項目 | 狀態 | 說明 |
|---|---|---|
| Redis client protocol compatibility | ✅ 完成 | 四條 production factory 固定 RESP2，Redis 5 本機服務可連線 |
| 本機 Redis real health／contract | ✅ 完成 | PING、TTL、JSON-safe cache、rate-limit、lease fencing |
| production shared-mode integration | ✅ 完成 | rate-limit、L2、single-flight、background lease paths |
| 雙 process／HTTP canary | ✅ 完成 | 兩個獨立 `app.py` worker 的跨 process consistency |
| fault injection／rollback probe | ✅ 完成 | fail-closed、local fallback、skip-round 與 safe-mode rollback |
| 本機 RDB backup／restore rehearsal | ✅ 完成 | source `bgsave`、隔離 restore service、sentinel read-back |
| synthetic observation／CI 替代驗證 | ✅ 完成 | bounded repeated health、TTL、rate-limit、lease cycles；GitHub Actions workflow 可重跑 |
| 正式 provider staging | ⏸ 未完成 | 尚無正式 provider instance／region／secret-store evidence |
| 正式 provider backup／restore | ⏸ 未完成 | 尚未建立 provider-native snapshot 或隔離 restore evidence |
| observation period | ⏸ 未完成 | 目前只有短時間 canary，沒有核准的持續觀測窗口 |
| 人工 rollout approval | ⏸ 未完成 | 尚未取得正式 promotion 核准記錄 |
| production multi-worker rollout | ⏸ 未完成 | production 仍維持 `--workers 1`，未切換正式 shared modes |

因此目前不是「五項正式條件中完成四項」，而是「五項正式條件均未宣稱完成；其
本機替代驗證與相容性／fault 證據已完成」。

## 替代驗證路線（2026-09-01）

已採納不改 production rollout 的替代方案：

- production 維持 `--workers 1`，四個 shared modes 維持 `local`。
- `regression/td03_synthetic_observation.py` 提供可調時長的 bounded synthetic soak，重複
  驗證 PING、shared cache TTL、sliding-window rate-limit 與 lease acquire／renew／release。
- `.github/workflows/td03-substitute-validation.yml` 使用隔離 Redis 7 service，依序執行
  staging contract、production shared-mode、雙 process HTTP canary 與 120 秒 synthetic
  observation。URL 只存在 workflow process environment，不寫入 repo 或輸出。
- 這些結果提升 CI 可重跑性，但不取代正式 provider-native backup／restore、核准觀測窗口、
  人工 rollout approval 或 production multi-worker rollout。

## 隔離服務

- Runtime：Windows portable Redis `5.0.14.1`，安裝於 workspace `.td03_runtime`。
- Binding：`127.0.0.1:6391`，protected mode 開啟。
- Data boundary：Redis DB 1、獨立 namespace；`save ""`、`appendonly no`，不作正式資料來源。
- Python client：既有 `redis==8.1.0`。
- Secret boundary：只以本次 process environment 注入 URL；未寫入 repo、文件或輸出。
- Cleanup：probe 使用隨機 keys，結束時依 namespace 清除；未觸碰 SQLite 或 `twse-cache.json`。

## 實連結果

執行：

```text
MARKET_PULSE_REDIS_URL=redis://127.0.0.1:6391/1
MARKET_PULSE_SHARED_STATE_NAMESPACE=market-pulse:staging:td03-real-20260901
python regression/td03_redis_staging_canary.py
```

結果：`TD03_REDIS_STAGING_CANARY_OK`。

- PING／短 TTL sentinel read-back：PASS；sentinel TTL `2s`。
- Redis version：`5.0.14.1`。
- ping latency：30 samples，p50 `0.165ms`、p95 `0.184ms`、p99 `0.199ms`、max `0.199ms`。
- JSON-safe cache TTL：PASS。
- sliding-window rate limit：PASS。
- owner-token fencing／renew／release：PASS。
- 兩個獨立 spawned processes：rate-limit 單一 accept、lease 單一 owner、cross-process cache read-back 均 PASS。
- disconnect／timeout fault injection：PASS，錯誤明確轉為 `SharedStateTimeout`，未靜默建立 local shared lock。

## Redis client 相容性修正

本機 portable Redis 5 不支援 redis-py 8 預設的 RESP3 `HELLO 3`。因此 probe
明確以 RESP2 連線。取得 TD-03 執行授權後，已將 security rate-limit 與 cache
L2／single-flight／background lease 四個既有 production factory 的 redis-py
client protocol 明確固定為 RESP2；這只改 wire compatibility，不改 shared-state
資料操作或 failure policy。修正後四個 factory 均能以本機 service 完成 PING。

`test_shared_state.py` 的 configured Redis contract 也已固定使用同一 protocol，
不再因 Redis 5 的 `HELLO 3` 而 skip。本次未把本機 Redis 謊稱為正式 provider staging。

若要進入下一批，應擇一：

1. 提供支援 RESP3 的 Redis／Valkey staging endpoint（優先），再做 provider／region／
   backup／restore 與 observation evidence；或
2. 維持已驗證的 RESP2 compatibility，並在正式 provider 上完成同一組 contract／latency／
   rollout gate。

## Production shared-mode probe

執行 `regression/td03_production_shared_mode_probe.py` 後結果為
`TD03_PRODUCTION_SHARED_MODE_PROBE_OK`：

- single process：四個 production shared-mode paths 均 PASS。
- dual process：rate-limit 單一 accept、single-flight 單一 leader、L2 cross-process read-back PASS。
- real disconnect：rate-limit fail-closed 503、cache L2 local fallback、single-flight local fallback、
  background lease skip-round PASS。

## HTTP dual-process canary

`regression/td03_http_dual_process_canary.py` 以兩個獨立 `app.py` process 執行（各自使用
temporary SQLite／cache path，共用同一 Redis namespace）：

- 兩個 worker `/api/health` 均回應 200。
- worker A 的 `/api/derivatives/v1-status` 首次請求回應 200。
- worker B 對同一 client 的下一次請求回應 429 `RATE_LIMITED`，證明 HTTP 層跨 process
  rate-limit consistency。
- 測試後兩個 process 均正常終止，temporary data 目錄清除。

Windows 的 Gunicorn package 需要 `fcntl`，無法啟動；因此以兩個獨立 Flask worker process
完成相同的 process-isolation canary，不將平台限制誤報為應用失敗。

## Secret-safe wrapper

`regression/td03_run_staging.ps1` 只從既有 process environment 讀取
`MARKET_PULSE_REDIS_URL`，不接受 URL command-line argument、不 echo URL；依序執行上述三組
probe，完成後自動把四個 shared mode flags 回到 `local` 再執行 H-11-04 gate。適用於本機 shell
或 CI secret store；wrapper 不會修改 `Procfile`、`render.yaml` 或正式環境變數。

CI workflow 不依賴 production secret；使用 workflow 內的隔離 Redis service。未來若要驗證
正式 provider，才由 CI secret store 注入 `MARKET_PULSE_REDIS_URL`，並另行取得人工核准。

## Rollout gate 與 rollback

`python regression/td03_h11_04_rollout_gate.py` 仍為
`TD03_H11_04_ROLLOUT_GATE_BLOCKED`／`eligible=false`：

- safe mode 與單 worker gate：PASS。
- 本次 real Redis probe 與 production shared-mode probe 證據已產出，但既有唯讀 gate 不會自動讀取
  新文件，仍將正式 provider backup／restore、observation period、manual rollout approval 標為未完成。
- 不切換四個 shared modes、不增加 worker、不修改 `Procfile`／`render.yaml`，不正式 rollout。
- 若後續 staging 變更失敗，rollback 順序仍為 shared modes → `local`、worker → `1`、
  再回退單一 adapter／deployment change。

## 驗證邊界

本證據只新增 real Redis staging runner 與紀錄文件；沒有更新 baseline、CSP、
production cache、SQLite 或部署設定。offline canary 與原有 H-11 文件仍保留，
作為正式 staging／人工核准前的安全護欄。
