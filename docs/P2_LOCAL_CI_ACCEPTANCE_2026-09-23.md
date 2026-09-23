# P2 local/CI acceptance evidence（2026-09-23）

## Scope

依專案負責人授權，P2 正式驗收不使用 Render，改採隔離的 local/CI ephemeral
Redis/Valkey runtime。此文件是 [優化作業基線_2026-09-21.md](優化作業基線_2026-09-21.md)
2026-09-23 修訂的 evidence index；不代表 production 已切換至多 worker。

## Environment contract

- Normative runtime: isolated Linux CI runner with ephemeral Redis/Valkey service.
- Local replay: existing portable/local Redis harness using a per-run namespace.
- Application runtime: two independent worker processes, equivalent to Gunicorn two-worker mode.
- Validation data: random per-run identities and exact namespace cleanup only.
- Production: unchanged; production worker safety contract remains `--workers 1`.
- Render: not used and not required by the amended P2 baseline.

## Evidence matrix

| P2 workstream | Evidence | Result |
|---|---|---|
| Redis/shared-state | `docs/TD03_LOCAL_REDIS_STAGING_EVIDENCE_2026-09-01.md` — Redis health/contract, production shared-mode integration, dual-process/HTTP canary, disconnect fault/rollback, local RDB rehearsal, bounded synthetic observation | PASS |
| ESM legacy evaluation | `docs/TD02_FULL_ESM_PHASE_3-4_closure_2026-09-01.md`, `docs/TD02_REMAIN_verification_closure_2026-09-01.md` — 21-page normal/rollback canary 42/42, removal conditions and rollback path recorded; classic fallback retained as safety net | PASS |
| High-risk builder/fetcher tests | `docs/TD10_REMAIN_01-03_evidence_2026-09-01.md`, `docs/REFACTOR_SUMMARY.md` — 10/10 top-risk functions with fixture/contract coverage and normal/empty/error branches | PASS |

## Backup and persistence boundary

- Application-managed backup: `PASS`.
- Application-managed restore: `PASS`.
- Provider-native backup/restore: `N/A` for ephemeral local/CI runtime; not claimed as PASS.
- No paid resource, Render resource, production environment, or production data was changed.

## Closure decision

Under the amended 2026-09-23 P2 acceptance environment, all three P2 workstreams have
evidence and rollback paths. P2 is complete as an evaluation/acceptance milestone;
production remains single-worker and no production rollout is implied.

`P2 = COMPLETE`

`PRODUCTION MULTI-WORKER ROLLOUT = NOT PERFORMED`

`PROVIDER-NATIVE BACKUP/RESTORE = N/A`

## Rollback

Revert the baseline-amendment and this evidence-index commit. Restore the prior baseline
interpretation and keep production at the existing single-worker configuration.
