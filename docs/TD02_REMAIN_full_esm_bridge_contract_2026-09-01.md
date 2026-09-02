# TD-02 全站 ESM bridge contract lock（2026-09-01；暫時封存）

本批將 TD02-01 的 895-symbol owner inventory 與 TD02-02 的 transitional bridge 設計落成 machine-readable allowlist。它不發布 global、不改 HTML、不切 production entry；正式 runtime wiring 仍須通過 browser-backed shadow／canary。

## 結論

- 狀態：`TD02_FULL_ESM_PHASE_2_CONTRACT_LOCKED_ARCHIVED_NO_PRODUCTION_SWITCH`。共鎖定 477 個 contract entries：required global bridge 468、entrypoint 5、window property 4。
- 每個 symbol 維持單一 source owner；`escapeHtml` 仍由 `js/core.js` 擁有，bridge 只能是 alias／adapter，不複製 function body。
- `runtime/bootstrap ↔ route/page-tw` 與 global-market cluster 兩組循環維持受控清單；未通過 deferred entry／cluster facade 的 browser proof 前不可切波。
- 本批 production wiring、HTML、baseline、classic fallback 均未變更；目前 browser backend 不可用，且依最新決定 Phase 3 接線與 Phase 4 收斂 gate 暫時封存。

## Bridge classes

| class | 內容 | 移除條件 |
|---|---|---|
| `named-symbol` | TD02-01 required global bridge allowlist | consumer 改成 named import 且 shadow verifier 綠燈 |
| `mutable-state` | state owner 的 getter／setter 過渡 adapter | 所有 reader／writer 改走 explicit store API 且 interaction 綠燈 |
| `entrypoint` | bootstrap 的 top-level route binding | 單一 ESM entry 完成 route import 且 canary 綠燈 |
| `window-property` | TWSE seed、payload handoff、innerHTML safety sentinel | 改成 explicit input／store／private safety adapter |

## Gate 與 rollback

正式接線前仍需每一 wave 的 browser-backed shadow、owner-publish／duplicate-run canary、正常／classic rollback canary，以及 21/21 page wiring、895/895 symbols、94/94 interactions、security、E2E 與 full verify。失敗時固定回退：ESM entry／bridge off → H-10 bundle → classic lockfile order；derivatives-status 另可回 classic addon。

完整 allowlist：`docs/TD02_REMAIN_full_esm_bridge_contract_2026-09-01.json`。
