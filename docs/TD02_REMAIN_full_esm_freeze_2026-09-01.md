# TD-02 全站 ESM 遷移前凍結與分波（2026-09-01；暫時封存）

本文件是 TD-02 全站 ESM 遷移的 Phase 1 freeze evidence。它只記錄目前 production wiring、895 symbols、21 頁與資產 fingerprint，不修改 HTML／JS／baseline。

> 歷史狀態註記：本文件記錄 Phase 1 凍結當下的狀態；Phase 3～4 已於同日後續授權完成，現況以 [`TD02_FULL_ESM_PHASE_3-4_closure_2026-09-01.md`](TD02_FULL_ESM_PHASE_3-4_closure_2026-09-01.md) 為準。

## 結論

- 狀態：`TD02_FULL_ESM_PHASE_1_FROZEN_ARCHIVED`。目前 ESM 頁面 1 頁，classic 頁面 20 頁。
- TD02-REMAIN-01～03 的 `derivatives-status.html` island 作為 W01 已完成；其餘 wave 尚未通過 browser-backed shadow gate。
- 本 freeze 不授權全站 production ESM switch；classic fallback、原 script order 與 rollback path 保留。

## Waves

| wave | pages | status |
|---|---|---|
| `W01-completed-status-island` | derivatives-status.html | `completed` |
| `W02-asset-hub` | bonds.html, derivatives-assets.html, international-finance.html, precious-metals.html | `pending-browser-shadow-gate` |
| `W03-global-market-and-derivatives` | derivatives-ai.html, derivatives-analytics.html, futures.html, options.html, us-market-overview.html, us-stocks.html | `pending-browser-shadow-gate` |
| `W04-tw-market` | market-overview.html, news.html, tw-etf.html | `pending-browser-shadow-gate` |
| `W05-us-market` | us-etf.html, us-stock-search.html, us-watchlist.html | `pending-browser-shadow-gate` |
| `W06-unclassified-followup` | index.html, tw-Optional-stocks.html, tw-stock-search.html, tw-stocks.html | `pending-browser-shadow-gate` |

## Required gate

全站切換前必須完成每一 wave 的 browser-backed shadow、explicit bridge、正常／rollback canary，並通過 21/21 page wiring、895/895 symbols、94/94 interactions、API、DOM／pixel、security／CSP、E2E 與 full verify。

在本 freeze 產出時沒有可用 browser backend；因此本文件只完成 freeze／分波，不得單獨據此宣稱 Phase 2～4 或全站 ESM 已完成。

完整 machine-readable freeze：`docs/TD02_REMAIN_full_esm_freeze_2026-09-01.json`。
