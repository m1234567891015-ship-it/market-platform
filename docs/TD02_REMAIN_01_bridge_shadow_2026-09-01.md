# TD02-REMAIN-01 ESM bridge contract／shadow proof

日期：2026-09-01  
狀態：✅ 本批 proof 通過；production wiring 未接線

## 範圍

本批選定最低風險的 `runtime/api ← js/api.js` 作為 shadow candidate。只在系統 temp
目錄建立一次性 ESM wrapper 與 classic fallback harness，沒有修改正式 HTML、bundle、
classic source、baseline、CSP、Service Worker、cache、部署設定、SQLite 或
`twse-cache.json`。

可重跑命令：

```text
python regression/td02_remain_01_bridge_shadow.py
```

通過輸出：`TD02_REMAIN_01_SHADOW_OK`

## Proof 結果

| gate | 結果 | 證據 |
|---|---|---|
| symbol inventory | ✅ | dependency matrix／global-symbol baseline 均為 895，unique owner 895 |
| bridge contract | ✅ | `runtime/api`、owner `js/api.js`、named export `fetchWithTimeout`、0 cross-module edge、0 global bridge symbol |
| ESM shadow runtime | ✅ | import 無 fetch side effect；success 保留 GET／AbortSignal；upstream error 與 timeout／AbortError 保留 |
| classic fallback | ✅ | classic source 可 publish `fetchWithTimeout`，status 204、GET options 與 AbortSignal 均保留 |
| escapeHtml | ✅ | 全站 definition 1 份，owner `js/core.js` |
| production wiring | ✅ | 21 頁；standard 與 derivatives-status addon wiring 均維持 TD18 minified order |
| error injection | ✅ | missing export、未註冊 global bridge、production wiring 變更均被 verifier 捕捉 |

## 六層驗證

- Python syntax：`regression/td02_remain_01_bridge_shadow.py` 通過。
- JavaScript syntax：`node --check js/api.js` 通過。
- Unit：`python -m unittest test_derivatives_platform.py`，176 tests PASS。
- Security：`security_guardrail_check.py`，16/16 PASS。
- E2E：`python e2e_smoke.py`，`E2E_SMOKE_OK`。
- Full verify：互動檢查通過；API live 與 20 頁 pixel compare 受目前環境外部資料／瀏覽器網路阻擋，回報既有 `[外部問題]`（TAIFEX／Yahoo 502、`ERR_NETWORK_ACCESS_DENIED`），未視為程式碼差異，也未更新 baseline。
- 逐位元組搬移比對：不適用；本批沒有搬移或正式 wiring 變更。

## 回退與下一步

回退只需移除 `regression/td02_remain_01_bridge_shadow.py` 與本 evidence；現行 TD18
minified entry 及 classic fallback 仍為正式依據。本批 proof 不授權正式 HTML ESM 接線；
下一批須另行驗證單一 module／route island migration。
