# TD-03 H-11 Redis 實連與多 worker staging rollout 封存紀錄

日期：2026-08-31  
狀態：⏸️ 暫不處理；已封存，未完成 rollout。本文件亦納入 TD-03 整體於 2026-09-01 的暫時封存依據。

## 封存範圍

本文件封存 H-11 尚未完成的 Redis 實連與多 worker staging rollout。H-11-01～H-11-04
的離線決策、shared-state contract、offline canary、rollout gate 與 rollback runbook
已完成；本文件不將它們誤標為實連或正式部署完成。

## 目前 gate 結果

- `MARKET_PULSE_REDIS_URL` 未由 secret store 注入。
- Redis PING／TTL sentinel、backup／restore 與 H-11-02 real Redis bucket contract：
  `not-run`。
- H-11-03 real dual-worker staging load、latency、disconnect／fault evidence：`not-run`。
- observation period 與 manual rollout approval：`blocked`。
- safe state 通過：shared modes 維持 `local`；`Procfile`／`render.yaml` 維持
  `--workers 1`，入口為 `app:app`。

因此 rollout eligibility 維持 `eligible=false`，並保留
`TD03_H11_04_ROLLOUT_GATE_BLOCKED` 結論。

## 暫不處理的原因

目前工作區只有 Redis Python client 與 Gunicorn，沒有可用的 staging Redis endpoint 或
`redis-server`。在沒有隔離 staging endpoint、secret、provider／region／namespace 與
backup／restore 證據前，不進行 provider provisioning、不以本機臨時服務替代 staging、
不切換 shared modes、不增加 worker、不發佈。

## 解封條件

重新授權並具備下列資料後，才可另立執行批次：

1. 由 staging secret store 注入隔離的 `MARKET_PULSE_REDIS_URL`，且輸出與紀錄不得洩漏
   secret。
2. provider、region、成本上限、namespace、backup／restore owner 與 checkpoint 已記錄。
3. Redis health／TTL、六個 JSON-safe L2 bucket、timeout／disconnect 與 fallback contract
   通過。
4. 雙 worker staging load、p50／p95／p99 latency、rate-limit fail-closed、single-flight
   與 background／options lease takeover／fencing 通過。
5. 完整驗證、觀測期與人工 rollout approval 完成。

## 恢復與回退順序

若未來解封後發生 shared backend、latency、lease ownership 或 API regression：

1. 關閉所有 shared modes，回到 `local`；
2. 恢復單 worker `--workers 1`；
3. 回退單一 adapter／deployment commit；
4. 保留 failure evidence 與 checkpoint，不修改 SQLite 或 `twse-cache.json`。

## 封存時驗證與限制

- H-11 專項測試：31 tests，30 PASS、1 skip（Redis URL absent）。
- security guardrail：16/16 PASS。
- H-11-04 verifier：`TD03_H11_04_ROLLOUT_GATE_BLOCKED`、`eligible=false`。
- 未修改 baseline、CSP、headers、`CACHE_VERSION`、Service Worker、`Procfile`、
  `render.yaml`、worker 數、Redis URL、SQLite 或 `twse-cache.json`。
- 既有 full verify 的外部資料／瀏覽器網路阻擋依規範標記為 `[外部問題]`，未更新 baseline。
