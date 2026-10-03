# Market Platform 投資決策系統優化與技術債稽核建議

## 1. 稽核結論

本次以「投資決策系統」與「軟體工程專案」兩條主線進行唯讀稽核，不修改任何專案檔案。

目前專案已不只是單純的市場 Dashboard，而是具備：

- 技術指標
- 市場廣度
- VIX / 波動率
- 法人資訊
- 期貨 / 選擇權
- Historical VaR
- Expected Shortfall
- Euler Risk Contribution
- 交易成本
- Backtest
- Decision Provenance
- Outcome Ledger
- Calibration
- Data Freshness / Provider Health
- 大量 Regression Test

因此下一階段最值得投入的方向，不是繼續增加更多 RSI、KD、MACD 類指標，而是把：

> 指標很多  
> → 決策可信度高  
> → 知道什麼市場環境下有效  
> → 知道什麼時候不該交易

做完整。

---

## 2. 建議優先級

| 優先級 | 項目 | 目前判定 | 對一般投資人的影響 |
|---|---|---|---|
| P0 | Data Quality 語意 | 有實際風險 | 可能把「資料完整」誤看成「資料品質很好」 |
| P0 | 情境百分比語意 | 容易誤解 | 可能把 heuristic 權重誤認為漲跌機率 |
| P0 | Decision → Outcome → Calibration | 後端已有基礎但未形成閉環 | 無法知道系統長期到底準不準 |
| P1 | Market Regime | 多處各自實作 | 不同頁面可能對同一市場做出不同狀態判斷 |
| P1 | Walk-Forward Backtest | 現有方法不差，但仍可升級 | 降低過度擬合與單一歷史期間偏誤 |
| P1 | 勝率改成 Expectancy | 建議升級 KPI | 防止高勝率但偶發大虧 |
| P1 | Decision Cockpit | 資訊很多但決策層可再簡化 | 一般投資人更容易看懂市場 |
| P2 | shared-calc.js / page JS 拆分 | 技術債明顯 | 降低前端修改互相影響 |
| P2 | builders.py / fetchers.py | 大型模組、耦合較重 | 維護與測試成本高 |
| P2 | Quant CI 完整性 | 發現 orphan regression | 部分量化測試可能沒有被 CI 強制執行 |

---

# 3. P0：Data Quality 語意應優先修正

目前 `derivatives/analytics.py` 的 `build_decision_quality()` 會建立：

- completeness
- freshness
- providerHealth
- consistency
- fallbackSource

設計方向正確。

但目前 unknown dimensions 可能被省略，最後只對已知 dimensions 取平均。

例如如果目前只知道 completeness：

```text
evidenceScore      = 100
dataQualityScore   = 100
dataQualityStatus  = AVAILABLE
```

即使不知道：

- Freshness
- Provider Health
- Fallback Source
- Cross-source Consistency

仍可能得到 Data Quality 100。

這會造成：

> 完整 ≠ 正確 ≠ 新鮮 ≠ 可交易

### 建議改成

至少拆成：

| 指標 | 意義 |
|---|---|
| Evidence Coverage | 必要資料有多少已取得 |
| Freshness | 資料是否即時 |
| Provider Health | 原始來源是否正常 |
| Cross-source Consistency | 多來源是否一致 |
| Fallback Status | 是否使用備援資料 |
| Quality Coverage | 品質維度有多少是真的知道 |

例如：

```text
Evidence Coverage   100
Data Quality         96
Quality Coverage     40%
Status               PARTIAL
```

比單純顯示：

```text
Data Quality 100
AVAILABLE
```

安全很多。

### 建議規則

Freshness 與 Provider Health 應列為 mandatory dimensions。

若任一關鍵品質維度缺失，不應將整體 Data Quality 標成完整 `AVAILABLE`。

---

# 4. P0：情境百分比不應被理解成統計機率

目前前端會產生：

```text
Bullish  58%
Neutral  27%
Bearish  15%
```

其來源主要是：

- trendScore
- ATR
- 技術狀態
- 規則權重
- normalization

這本質上較接近：

> Scenario Weight

而不是：

> P(上漲) = 58%

即使 UI 已有 caveat，一般投資人仍很容易把百分比理解為勝率或預測機率。

### 建議改為

```text
多方情境權重   58
震盪情境權重   27
空方情境權重   15

尚未經統計機率校準，以上不是實際漲跌機率。
```

在 calibration 尚未成立以前，甚至可避免使用 `%`。

例如：

```text
多方權重   高
震盪權重   中
空方權重   低
```

只有真正完成 OOS Calibration 後，才顯示 Probability Label。

---

# 5. 建立 Decision → Outcome → Calibration 完整閉環

目前專案其實已具備相當重要的基礎：

## 已存在

### Calibration

`derivatives/calibration.py`

包含：

- Brier Score
- Calibration Buckets
- OOS Calibration
- probability_label_allowed()

### Outcome Ledger

`derivatives_store.py`

已有：

- record_decision()
- evaluate_decision_outcome()
- list_decision_outcomes()

並能處理：

- LONG
- SHORT
- 未來價格
- MFE
- MAE
- Target Hit
- Stop Hit
- Transaction Cost
- Data unavailable

---

## 建議真正串成

```text
市場資料
   ↓
Decision
   ↓
Decision Ledger
   ↓
T+1 / T+5 / T+20 / T+60
   ↓
Outcome Evaluation
   ↓
Calibration
   ↓
各分數區間真實歷史表現
   ↓
模型權重修正
```

---

## 每次 Decision 應永久記錄

```text
Decision Time
Asset
Price
Market Score
Direction
Market Regime
Volatility Regime
Evidence Score
Data Quality
Model Version
Strategy Version
```

之後計算：

```text
T+5 Return
T+20 Return
T+60 Return
MFE
MAE
Target Hit
Stop Hit
Net Return
Outcome
```

累積足夠樣本後再統計：

```text
Score 80-100
Sample Count: 516
20D Correct Rate: 64.1%

Score 60-79
Sample Count: 923
20D Correct Rate: 55.8%
```

這才是系統真正知道自己「準不準」的方法。

---

# 6. 不應只追求勝率，應升級為 Expectancy

高勝率不代表高報酬。

例如：

## 策略 A

```text
勝率 80%
平均獲利 +1%
平均虧損 -8%
```

期望值：

```text
EV = 0.8 × 1% - 0.2 × 8%
   = -0.8%
```

雖然勝率高，但長期仍可能虧損。

## 策略 B

```text
勝率 45%
平均獲利 +6%
平均虧損 -2%
```

期望值：

```text
EV = 0.45 × 6% - 0.55 × 2%
   = +1.6%
```

勝率較低，反而具正期望值。

---

## 建議核心 KPI

不要只看 Win Rate，至少一起使用：

```text
Net Expectancy
Profit Factor
Max Drawdown
Expected Shortfall
Sharpe
Win Rate
Average Win
Average Loss
MFE
MAE
Turnover
Transaction Cost
Sample Count
```

---

# 7. 建立統一 Market Regime Engine

目前不同頁面已存在：

- Risk-On / Risk-Off
- Bull / Bear
- Trend
- Volatility
- Options Regime
- Futures Regime
- TW Regime

但若由不同頁面各自實作，可能出現：

```text
台股頁      偏多
期貨頁      中性
選擇權頁    Risk-Off
Global      Risk-On
```

對一般投資人容易造成混亂。

---

## 建議建立統一 Contract

```text
MarketRegimeModel
```

輸出：

```text
Trend Regime
- Bull
- Range
- Bear

Volatility Regime
- Low
- Normal
- High
- Stress

Liquidity Regime
- Normal
- Tight

Breadth Regime
- Broad
- Narrow
- Deteriorating

Macro Regime
- Risk-On
- Neutral
- Risk-Off

Confidence
- Strong
- Medium
- Weak

Data Quality
- Available
- Partial
- Stale
```

所有：

- 台股
- 美股
- ETF
- Futures
- Options
- Portfolio
- AI

共用同一份 regime 判定。

---

# 8. 回測應升級成 Regime Conditional

不要只回答：

```text
MACD 金叉
歷史勝率 61%
```

應該改成：

```text
MACD 金叉

全部市場
Win Rate       57%
Profit Factor  1.23

Bull + Low Vol
Win Rate       68%
Profit Factor  1.92

Bull + High Vol
Win Rate       55%
Profit Factor  1.18

Range Market
Win Rate       44%
Profit Factor  0.87

Bear Market
Win Rate       38%
Profit Factor  0.72
```

這樣一般投資人才知道：

> 不是某個指標有沒有用，而是它在什麼市場狀態下有用。

---

# 9. Backtest 再升級 Walk-Forward Validation

現有 Backtest 已具備：

- Train
- Validation
- Test
- Chronological Split
- Purging
- Embargo
- Transaction Cost
- Next-bar Execution
- Stop Loss
- Take Profit
- Profit Factor
- Max Drawdown
- Losing Streak
- Out-of-sample Drift

這部分應保留。

下一階段建議增加 Walk-Forward：

```text
2018-2020 Train
2021 Validate

2019-2021 Train
2022 Validate

2020-2022 Train
2023 Validate

2021-2023 Train
2024 Validate

2022-2024 Train
2025 Validate
```

最後觀察的是：

```text
Performance Stability
```

而不只是單次 60 / 20 / 20 切割。

---

# 10. 一般投資人 UI 建議改成三層決策

## 第一層：現在是什麼趨勢？

| 週期 | 趨勢 | 強度 |
|---|---|---:|
| 5D | 偏多 | 72 |
| 20D | 多頭 | 81 |
| 60D | 震盪 | 55 |
| 120D | 多頭 | 68 |

---

## 第二層：現在有多危險？

| 風險 | 狀態 |
|---|---|
| 市場波動 | 高 |
| 流動性 | 正常 |
| 趨勢反轉 | 中 |
| 尾端風險 | 高 |
| 部位集中 | 低 |
| 資料品質 | 良好 |

---

## 第三層：為什麼？

```text
支持多方
✓ MA20 > MA60
✓ 市場廣度改善
✓ 法人連續買超
✓ VIX 下降

反對訊號
⚠ RSI 過熱
⚠ 選擇權 PCR 惡化
```

只有需要更深入分析時，再展開：

- RSI
- MACD
- DMI
- OBV
- ATR
- Fibonacci
- SMC
- OI
- PCR
- Basis

核心原則：

> 先結論 → 再原因 → 最後原始指標

---

# 11. Risk Score 應拆成不同風險類型

目前不同模組都有 `riskScore`，但其含義不同。

建議統一拆為：

## Market Risk

市場本身的風險，例如：

- Volatility
- Breadth
- Liquidity
- Macro Stress

## Signal Risk

訊號自身不確定性，例如：

- 技術指標衝突
- 資料不足
- Data Quality
- Signal disagreement

## Strategy Risk

交易策略風險，例如：

- Leverage
- Gamma
- Theta
- Slippage
- Stop distance
- Liquidity

## Portfolio Risk

資產組合風險，例如：

- VaR
- ES
- Concentration
- Correlation
- Risk Contribution

避免所有風險都統稱為同一個 `Risk Score`。

---

# 12. 已完成且建議保留的 Quant 基礎

目前抽查到的核心量化能力包括：

- Historical VaR
- Expected Shortfall
- Euler Risk Contribution
- Sharpe / Return Semantics
- Futures Asset Cost Model
- Futures Execution Costs
- Point-in-Time Integrity
- Immutable Decision Provenance

這些底層不建議推翻重做。

下一階段應以「串接、校準、驗證」為主。

---

# 13. Regression / CI 技術債

發現：

```text
regression/test_q2_backtest_methodology.js
```

其中包含：

```text
signalTiming === "T close"
```

但目前測試出現：

```text
actual = undefined
```

進一步判斷，目前 `buildBacktestLearningModel()` 已開始要求：

```text
options.assetClass
```

若缺少 assetClass，會 fail-close。

舊 Q2 test fixture 可能仍以舊 contract 呼叫。

因此較可能是：

> Regression fixture 沒有跟新的 cost-model contract 同步。

此外目前 workflow 中未明確發現該 test 被 CI 強制執行。

這屬於典型：

> Orphan Regression Test

---

## 建議處理方式

```text
修正 fixture
→ 明確傳入 assetClass
→ 驗證 PASS
→ 納入 Quant CI
```

若該測試已完全被新測試取代，則應正式 retire，而不是持續留在 repo 卻沒有人執行。

---

# 14. 大型模組仍是主要工程技術債

目前可看到大型模組，例如：

```text
builders.py
約 7,377 lines

fetchers.py
約 5,189 lines

shared-calc.js
約 4,000 lines
```

部分前端 page script 亦達數千行。

長期風險：

- 修改 A 影響 B
- Regression 範圍變大
- 單元測試困難
- Domain ownership 不清楚
- Debug 成本提高
- AI / Codex 修改容易產生跨功能副作用

---

## 建議拆分方向

### Python

```text
builders/
  market/
  portfolio/
  derivatives/
  risk/
  analytics/

fetchers/
  twse/
  taifex/
  fred/
  treasury/
  us_market/
```

### Frontend

```text
shared/
  trend/
  risk/
  regime/
  portfolio/
  backtest/
  formatting/
```

避免單一大型檔案負責太多不同 domain。

---

# 15. shared-calc.js 建議移除 Hidden Global State

部分 calculation function 仍可能隱含讀取全域：

```text
data
```

例如：

- marketInternationalIndexes
- marketMacroFactors
- marketVolatility
- marketOverview

這種設計會讓：

```text
同一個 function(input)
```

可能因 global state 不同而輸出不同結果。

影響：

- Unit Test
- Replay
- Backtest Reproducibility
- Decision Provenance

---

## 建議改為顯式 Input

不要：

```javascript
calculateXXX()
```

裡面偷讀 global data。

改成：

```javascript
calculateXXX({
    internationalIndexes,
    macroFactors,
    volatility,
    marketOverview
})
```

讓 calculation function 盡量 pure。

---

# 16. Portfolio Missing Data 不應直接視為 0

目前部分 Portfolio historical return 計算若沒有歷史資料，可能 fallback 到：

```text
0
```

但：

```text
Missing
```

與：

```text
0% Return
```

不是同一回事。

若大量資產沒有資料，會把 Portfolio Momentum 人為拉向中性。

---

## 建議改成

```text
Portfolio Momentum: +4.2%
Coverage: 72%
Status: PARTIAL
```

不要用 0 代表 missing。

---

# 17. 建議最終架構

```text
                MARKET DATA
                    │
        ┌───────────┼────────────┐
        ▼           ▼            ▼
     Trend        Risk        Market Regime
        │           │            │
        └───────────┼────────────┘
                    ▼
              Signal Engine
                    │
                    ▼
            Decision Quality
          ┌─────────┼─────────┐
          ▼         ▼         ▼
      Evidence   Freshness   Conflict
                    │
                    ▼
               Decision
                    │
               ┌────┴────┐
               ▼         ▼
             Trade     No Trade
               │
               ▼
           Outcome Ledger
               │
               ▼
          OOS Calibration
               │
               ▼
        Regime Performance
               │
               ▼
           Model Update
```

---

# 18. No Trade 應成為正式決策

真正好的投資系統不應每天都產生買賣建議。

應該能正式判斷：

```text
NO TRADE
```

可能原因：

- Data Quality 不足
- Signal Conflict 過高
- Regime 不適合
- Expected Value 不夠
- Transaction Cost 過高
- Tail Risk 過高
- Sample Count 不足

投資平台應能清楚告訴使用者：

> 現在沒有足夠優勢，不值得承擔風險。

這本身就是重要的投資決策。

---

# 19. 建議執行順序

## 第一階段：決策語意完整性

```text
Data Quality Coverage
→ Scenario Weight 非機率化
→ Risk Score 分類
→ No-Trade State
```

## 第二階段：決策結果閉環

```text
Decision
→ Outcome
→ Calibration
→ Score Bucket
→ Regime Performance
```

## 第三階段：模型驗證

```text
Walk-Forward
→ Regime-conditioned Backtest
→ Net Expectancy
→ Model Drift
```

## 第四階段：工程結構債

```text
builders / fetchers 拆 Domain
→ shared-calc 去除 Global State
→ Giant Page Modules 拆分
→ Quant CI 統一
```

---

# 20. 最終判定

目前專案真正缺少的已經不是「更多技術指標」。

下一個成熟階段應該是：

> 從「分析很多」升級成  
> 「知道自己的分析何時可信、何時不可信，以及過去到底有沒有證明自己有效」。

尤其目前專案已具有：

- Decision Provenance
- Outcome Ledger
- Calibration
- Historical VaR / ES
- Transaction Cost
- OOS Backtest

這些重要基礎。

因此最值得投入的主線為：

```text
Market Regime
→ Decision Ledger
→ Outcome Evaluation
→ OOS Calibration
→ Regime-conditioned Expectancy
```

這條主線完成後，才會真正提升一般投資人對：

- 市場趨勢
- 市場風險
- 訊號可信度
- 策略適用環境
- 真實期望值
- 是否應該交易

的辨識能力。

---

## 稽核模式

本文件基於本次專案 ZIP 的唯讀稽核結果整理。

**未修改原始 ZIP，未修改專案程式碼，未推進任何開發流程。**
