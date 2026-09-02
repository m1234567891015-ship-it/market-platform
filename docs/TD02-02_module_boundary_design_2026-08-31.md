# TD02-02 模組邊界、命名、載入契約與 verifier 方案（2026-08-31）

## 0. 批次界線

本文件是 TD02-02 的設計產物，承接 [TD02-01 依賴矩陣](TD02-01_dependency_matrix_2026-08-31.md)。
本批只定義候選 module boundary、命名、載入／初始化契約、legacy global bridge 契約、回退方式
與 verifier 方案；**不建立 ESM 檔案、不修改任何 `<script>`、不搬動函式、不移除 classic slices、
不修改 baseline/CSP/headers/Service Worker/cache/deployment/SQLite/twse-cache.json**。

現行 production wiring 仍是 `common-runtime.js → route-bundle.js`；
`derivatives-status.html` 再載入 `derivatives-status-addon.js`。現行 classic fallback 仍依
TD02-01 lockfile 順序保留。

## 1. 設計原則

1. **先保留行為，再收斂 global scope。** ESM candidate 先以 shadow／canary 方式驗證，不能把
   「改成 import」本身當成行為正確的證據。
2. **source owner 與 semantic owner 分開記錄。** TD02-01 的 895 個 symbol source owner 是
   過渡期唯一宣告 owner；若未來要把安全 sentinel 或 loader re-home，必須建立明確的 owner
   migration record，不得複製一份或讓兩個模組同時定義。
3. **跨 module 只允許三種邊：named import、明確 bridge、明確 deferred callback。** 禁止以
   `window[name]` 動態查找來掩蓋未知依賴，禁止新增 inline script、`eval` 或 `unsafe-*` CSP。
4. **可變狀態不可直接以 ESM imported binding 互相寫入。** state module 需提供明確的 read／
   write API 或單一 store；純函式計算則以參數／回傳值傳遞。
5. **classic fallback 是可操作的回退，不是文件口號。** 每個 shadow／canary verifier 都必須
   能在同一份 source 與 HTML 上切回現行 classic entry 並重新跑既有護欄。

## 2. 候選 module boundary 與命名

候選名稱採 `runtime/*`、`route/*`、`compat/*` 三個 namespace。下表的 candidate module 是
邏輯邊界；本批不建立對應目錄，既有 source slice 與 H-10 bundle 輸入仍是唯一現況來源。

| 現行 source slice | candidate module | boundary owner | 對外契約 | 遷移備註 |
|---|---|---|---|---|
| `pwa.js` | `runtime/pwa` | PWA controls／service-worker sync | `startPwaRuntime()`（shadow contract） | 維持獨立 IIFE；不把 PWA state 混進 market state |
| `js/state.js` | `runtime/state` | 共享可變 state、constants、localStorage adapter | `marketState`、typed read/write adapters、storage adapters | 895 symbols 的過渡 owner；禁止 route module 直接互改 imported binding |
| `js/core.js` | `runtime/core` | format／parse／URL safety／innerHTML safety | named pure helpers、`escapeHtml`、`safeUrl`、`installInnerHtmlGuard()` | `nativeInnerHtmlDescriptor` 的現行 source owner 仍以矩陣為準；語意上由 safety boundary 管理 |
| `js/api.js` | `runtime/api` | fetch／timeout／endpoint wrapper | `fetchWithTimeout`、endpoint-specific API functions | 不直接讀 route state；錯誤形狀維持現有 contract |
| `js/shared-calc.js` | `runtime/shared-calc` | 純技術／財務計算 | named pure calculators | 依賴 state/core 的既有邊逐項改成 import 或 adapter，不新增 global |
| `js/render-shared.js` | `runtime/render-shared` | 共用 DOM renderer／navigation／portfolio UI | named renderers + DOM-safe helpers | 依賴 core/state/api/calc；不反向 import route entrypoint |
| `js/charts.js` | `runtime/charts` | chart drawing／zoom／hover | named chart renderers／bindings | 只依賴 shared runtime；不得由 charts 反向觸發 page initializer |
| `js/stock-detail.js` | `route/stock-detail` | 個股 detail closure | `renderStockDetail` facade、detail loaders | 先保持整體 closure；內部再拆另批處理 |
| `js/page-home.js` | `route/page-home` | home／market page render | `renderHome`、`renderMarketPage` | route-specific；資料載入由 shared loader contract 提供 |
| `js/page-us.js` | `route/page-us` | US search／ETF／watchlist | page init/render facades | 不直接持有 global-market payload；使用明確 context adapter |
| `js/page-tw.js` | `route/page-tw` | TW sectors／search／watchlist／ETF | `initSearchPage`、`initWatchlistPage`、TW page facades | 與 bootstrap 的循環由 `runtime/live-data` contract 解開 |
| futures/options/assethub 三 slice | `route/global-market` module island | global-market orchestration cluster | `initGlobalMarketPage`、`renderGlobalMarketPage`、cluster context | 三個 slice 先視為一個 ESM migration island；不在 TD02-02 內強行拆除內部循環 |
| `js/main.js` | `runtime/bootstrap` | DOM entry／page dispatch／poll scheduling | `startApp()`、`renderCurrentPage()`、loader registration | 所有 route import 完成後才啟動；top-level side effect 改由 entry contract 管理 |
| `js/legacy-unclassified.js` | `route/legacy-unclassified` | 未分類 legacy symbols | allowlisted legacy exports only | 空 compatibility slot 保留；不得在本批刪除或自動歸類 |
| `app.js` | `compat/app-shell` | classic compatibility shell | no new exports | 保留空殼與 classic fallback 位置 |
| `derivatives-ui.js` | `route/derivatives-status-addon` | status page addon | addon entry | 維持 route-bundle 後的專用尾端載入契約 |

### 2.1 建議的 future physical layout（未建立）

若 TD02-03／後續接線獲得授權，候選 physical layout 為：

```text
js/modules/runtime/{pwa,state,core,api,shared-calc,render-shared,charts,live-data,bootstrap}.js
js/modules/route/{stock-detail,page-home,page-us,page-tw,global-market/index,legacy-unclassified}.js
js/modules/compat/{legacy-global-bridge,app-shell}.js
js/modules/route/derivatives-status-addon.js
```

這只是命名與 ownership contract，不代表現在可建立上述檔案；`runtime/live-data` 是為解開
`main ↔ page-tw` 的語意邊界所預留的設計節點。

## 3. Import／export／global bridge 契約

### 3.1 Symbol ownership

- `docs/TD02-01_dependency_matrix_2026-08-31.json` 的 `symbols[*].source` 是目前唯一 source
  owner；同一 symbol 不得在兩個 candidate module 定義。
- `function`、constant、read-only config 可先以 named export 遷移。
- 目前會被重新賦值的 state symbol 不直接 export mutable primitive；改由
  `runtime/state` 的 `marketState`／明確 getter-setter 或 command API 管理。實作前必須以
  symbol-level write inventory 補齊 read/write evidence。
- `escapeHtml` 只有 `runtime/core` 一個 semantic owner；任何 legacy exposure 都只能是
  bridge alias，不得是第二份 function body。

### 3.2 Transitional bridge

建議的 bridge logical module 為 `compat/legacy-global-bridge`，但本批不建立。其契約分四層：

| bridge class | 允許內容 | owner／移除條件 |
|---|---|---|
| `named-symbol` | TD02-01 `required_global_bridge` 中的明確 allowlist | consumer 改成 named import 且 shadow verifier 通過後移除 |
| `mutable-state` | state store 的 getter／setter adapter，不暴露任意 `window[name]` | 所有 writer／reader 完成 store migration 且 interaction 全綠 |
| `entrypoint` | bootstrap、route initializer 的 deferred callback | 對應 HTML／module entry 改由單一 ESM entry 控制後移除 |
| `window-property` | 僅 `TWSE_DATA`、`TWSE_ALL_STOCKS`、`currentGlobalMarketPayload`、innerHTML safety sentinel 等矩陣列出的契約 | 各 property 改成 explicit input／store／private adapter 後移除 |

Bridge 必須具備：

- 靜態 allowlist：`consumer → symbol → owner → bridge class → removal gate`；任何未登錄 symbol
  直接掛到 `window` 都 fail closed。
- owner assertion：同一 symbol 只能 publish 一次；重複 publish、shadowed writer、未授權
  consumer 都是 verifier failure。
- phase assertion：top-level immediate reference 在 module evaluation 前必須已由 import 或
  bridge 提供；不能等 DOMContentLoaded 才補一個 evaluation-time 依賴。
- rollback switch：bridge／ESM entry 失敗時，harness 立即切回 classic entry；不得修改
  production HTML 或基準檔案來「修」差異。

### 3.3 Dynamic window properties

- `TWSE_DATA`／`TWSE_ALL_STOCKS`：視為外部 seed input，由 `runtime/state` 的初始化 adapter
  讀取；不能改成跨 route global。
- `currentGlobalMarketPayload`：視為 global-market context store；由 global-market island
  擁有，page-us／options 的 writer 與 futures 的 reader 透過 explicit context API 過渡。
- `__MARKET_PULSE_SAFE_INNER_HTML__`：視為 safety adapter 的私有 idempotence sentinel；只准
  safety boundary 讀寫。

## 4. 載入與初始化契約

### 4.1 Current production／fallback（本批不改）

| 模式 | 執行順序 | 用途 |
|---|---|---|
| production | `common-runtime.js → route-bundle.js` | 現行 20 個一般頁面 |
| production status | `common-runtime.js → route-bundle.js → derivatives-status-addon.js` | status 專用 addon |
| classic fallback | `pwa.js → state → core → api → shared-calc → render-shared → charts → stock-detail → page-home → page-us → global-market-futures → global-market-options → global-market-assethub → page-tw → legacy-unclassified → main → app.js` | H-10 bundle／ESM 失敗時的回退順序 |
| classic fallback status | 上列順序後加 `derivatives-ui.js` | status 回退 |

### 4.2 Future ESM entry contract（未接線）

1. HTML 只會有一個受控 module entry；entry 先 import runtime，再 import route facades，最後
   呼叫 `startApp()`。本批不修改 HTML。
2. `runtime/state` 初始化必須先於 `runtime/core` safety guard；TD02-01 已標出
   `nativeInnerHtmlDescriptor` 的 evaluation-time edge。
3. route module 的 function-body late reference 可由 import graph 提供；但
   `runtime/bootstrap` 的四個 immediate refs（`initSearchPage`、`initWatchlistPage`、
   `initGlobalMarketPage`、`loadYahooSectorCategory`）必須在 entry evaluation 前完成 binding。
4. DOM initializer 只能註冊一次。`startApp()` 必須以目前 `DOMContentLoaded`／bootstrap 順序為
   contract，避免 classic 與 ESM shadow 同頁雙重 fetch、雙重 event listener 或雙重 polling。
5. `runtime/live-data` 擁有 `loadLiveData` semantic contract；`runtime/bootstrap` 與
   `route/page-tw` 都只 import 它，不互相 import，消除 `main ↔ page-tw` 的 cycle。
6. global-market futures/options/assethub 初期視為同一 module island，內部以 cluster context
   與一個 public facade 接出；只有另批 proof 證實拆分安全後，才允許細拆 island。
7. `derivatives-status-addon` 仍是最後的 page-specific entry，不得被一般 route entry
   隱式載入。

## 5. 循環依賴處理決策

| SCC | TD02-02 決策 | 不採用的作法 |
|---|---|---|
| `runtime/bootstrap ↔ route/page-tw` | 預留 `runtime/live-data` 作共同 loader contract；bootstrap 與 page-tw 均向它依賴 | 不靠把 `main.js` 放最後來掩蓋 ESM cycle |
| global-market futures/options/assethub | 第一階段視為 `route/global-market` module island；對外只提供 facade/context | 不在沒有 shadow proof 時任意拆函式、複製 helper 或重排三個 source |
| `runtime/core → runtime/state` | 保留 evaluation-time import；後續可評估把 safety descriptor 內聚至 core，但需 owner migration record | 不在 core 內複製 descriptor 或把 guard 延後到 DOMContentLoaded |

## 6. Verifier 方案

本節定義後續可實作的 verifier contract；TD02-02 不新增正式 runtime verifier，也不修改既有
`security_guardrail_check.py`。未來 verifier 應在隔離 temp 目錄執行，不寫入 SQLite、
`twse-cache.json`、baseline 或 production assets。

### 6.1 Static manifest gate

輸入：TD02-01 JSON、future module manifest、TD-18 lockfile、21 HTML、classic source slices。

必測斷言：

1. 21 頁、895 symbols、每個 symbol 恰好一個 source owner；manifest 與 TD02-01 JSON 的
   owner hash 不一致即 fail。
2. 每個 import／bridge edge 都能對到 `from → symbol → owner → candidate module`；未知 edge、
   duplicate owner、未登錄 dynamic window property 即 fail。
3. SCC 只允許本文件列出的兩個受控處理單元；新增循環必須停止 rollout。
4. top-level immediate refs 必須全部落在同檔、較早 runtime import 或明確 entrypoint bridge；
   尤其檢查 core safety guard 與 bootstrap 四個 immediate refs。
5. `escapeHtml` function body 只能有一份；bridge alias 不計為第二份 body，但必須有 owner。
6. 所有 module／bridge 檔案通過 `node --check`；不得出現 inline script、`unsafe-inline`、
   `unsafe-eval`、`eval` 或 `new Function`。

### 6.2 Shadow runtime gate

shadow 只在隔離 harness／browser context 載入，不接 production HTML。每個代表性 page 至少
核對：

- global surface：classic baseline 895/895 owner、允許 bridge allowlist、無額外 global pollution；
- `escapeHtml` 單一來源與 innerHTML guard 已在 DOM 輸出前生效；
- initializer／event listener／polling 各只註冊一次；
- local asset 404=0、CSP 維持 `script-src 'self'` 與 `frame-ancestors 'none'`；
- API response schema、錯誤狀態與 fallback message 與 classic context 一致；
- DOM 實質內容、pixel diff、P0/P1 interaction 與 console/network error 分類均可比對。

### 6.3 Rollback gate

任何 static gate、symbol、CSP、DOM、pixel、interaction、API 或 error gate 失敗時：

1. 停止 ESM shadow/canary，不擴大頁面範圍。
2. harness 切回 H-10 production bundle 或 classic fallback；確認 21 頁／94 條 interaction。
3. 保留 failure evidence，不更新 baseline、CSP、Service Worker、cache version 或部署設定。
4. 只有重新完成 owner／bridge manifest 與 full verify，才可提出下一批授權。

### 6.4 最小錯誤注入驗收

正式 verifier 交付前至少注入以下錯誤，確認每項都能 fail：

- 移除 `escapeHtml` import 或改接第二份 function body；
- 把 `runtime/state` 延後到 core 之後，觸發 safety descriptor evaluation failure；
- 刪除 bootstrap 的一個 route import；
- 讓 `currentGlobalMarketPayload` writer 不再更新；
- 將 global-market island 的一個 callback 改成未登錄 bridge；
- 讓 entrypoint 重複註冊 DOMContentLoaded／polling。

## 7. 回退與下一批輸入

TD02-02 本批的回退是移除本設計文件，不改現行 runtime。未來實作批次若已接線，固定回退
順序為：

```text
ESM entry / bridge off
  → H-10 production bundle entry
  → classic source order from td18_shadow_build.lock.json
  → derivatives-ui.js addon only on derivatives-status.html
```

TD02-03 的輸入應是：一個低風險、可隔離的 runtime／route candidate、對應 bridge allowlist、
一頁 shadow harness、上述 static／runtime／rollback gate，以及錯誤注入證據。TD02-03 未獲
授權前，不得建立 ESM module 或改接正式 HTML。

