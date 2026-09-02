# TD-15 R3 JS residual audit（2026-08-31）

本報告是 R3 現況重核，唯讀、不刪除 JS、不更新 baseline。

## 結論

- 狀態：`R3_PASS_NO_DELETION`。歷史 snapshot 仍記錄 52 個第一層與 6 個第二層 observe，但目前已不存在可刪除的 residual symbol。
- `js/legacy-unclassified.js` 目前為 0 bytes、0 個 top-level declaration。
- 58 個歷史符號在目前 HTML／JS／CSS／Python 執行來源的 literal hit 總數為 0。
- JS `window[...]` sites 共 8 個；命中歷史 TD-15 symbol 的 dynamic site 為 0 個。
- H-04-11～H-04-15 已記錄的五條觀察呼叫鏈不重複處理；本批沒有 source 或 baseline deletion。

## 三方證據

1. **目前 source／AST owner**：legacy isolation file 為空，沒有 52/6 snapshot 的現存 declaration。
2. **repo literal scan**：排除 docs、baseline、`.tmp` 與 `.git` 後，58 個歷史符號在 HTML、JS、CSS、Python 中均為零命中。
3. **dynamic access**：目前 JS 仍有一般 `window[...]`，但其 expression 均未命中 58 個歷史符號；不存在可解析到這批候選的動態入口。

## 驗收範圍

- frontend：21 頁。
- interaction：94 條 steps。
- global-symbol baseline：由既有 `td02_01_dependency_matrix.py --check` 另行確認，R3 不更新 baseline。

## 決策

R3 不執行 deletion。未來若出現新 JS residual，必須另以新 symbol、root/caller/callee、HTML/event/window 入口與 ≤20 symbols 的獨立批次重新建立證據；不得回溯刪除已完成的 H-04-11～H-04-15 鏈。

## REMAIN closure（2026-09-01）

R3 結果已被 TD15-REMAIN closure 採用：58 個歷史符號維持零 declaration／literal／dynamic hit，沒有新增 JS deletion batch。TD15-REMAIN-07 的 CSS closure 亦已完成，未修改本批 JS 結果。
