# P2-03 Historical Research Feature Contract V1

**Contract ID:** `P2_03_HISTORICAL_RESEARCH_FEATURES_V1`  
**Model ID:** `P2_03_HISTORICAL_RESEARCH_LOGISTIC_V1`  
**Classification:** `RESEARCH_ONLY / NOT_PRODUCTION / NOT_PROSPECTIVE`  
**Evidence class:** `HISTORICAL_RESEARCH_AS_OF_OOS`

This contract is separate from `P2_03_DERIVATIVES_SCORE_FEATURES_V1`. It does not contain, infer, or substitute for production `dataQualityScore`, and its pairs do not count toward prospective calibration minimums.

## Input and availability audit

Input is the already inventoried TAIFEX TX main-contract daily dataset at `.tmp/p203-historical-asof-replay/taifex_tx_daily_normalized.json`, SHA-256 `90b5f772a19e230d2212f66a1c522be0e95801f03fd8079d33235a16d3106930`. It has 400 strictly increasing, unique sessions from 2024-12-06 through 2026-10-01. The fields `open`, `high`, `low`, `close`, `changePct`, `volume`, `openInterest`, and `settlement` are present and non-null in all rows. `contractMonth` changes through the series. Feature V1 uses only `high`, `low`, `close`, and `openInterest`; volume, settlement, open, and exchange `changePct` are excluded to keep the contract small and avoid extra semantics.

The source is a current historical export, not an archived daily vintage. The market-date observations and any subsequent corrections cannot be independently proven to have been available in this exact form at the historical cutoff. Accordingly, the replay enforces strict chronological row cutoffs and reports this source-vintage limitation; it does not claim independently verified historical publication-time provenance.

## Feature definitions

For forecast decision session `D`, use only rows through `D`:

| Feature | Formula | Lookback |
|---|---|---:|
| `momentum_5` | `close[D] / close[D-5] - 1` | 5 prior session intervals |
| `range_pct_1` | `(high[D] - low[D]) / close[D]` | Current decision session only |
| `open_interest_change_1` | `openInterest[D] / openInterest[D-1] - 1` | 1 prior session interval |

Non-finite values, non-positive denominators, missing fields, or non-increasing/duplicate dates make that row ineligible; no imputation is performed. The first five sessions are warm-up exclusions. Features are not selected or changed after calibration metrics are inspected.

For each forecast, standardization uses only the matured prior training rows available at that forecast cutoff. Means and population standard deviations are computed per feature from those rows. A zero standard deviation maps that standardized feature to zero. No full-sample statistics, clipping, future values, or future extrema are used.

## Research direction, target, and horizon

Production decision states cannot be reconstructed from this source. V1 therefore defines the independent research-only direction `RESEARCH_LONG` when `momentum_5 > 0` and `RESEARCH_SHORT` when `momentum_5 < 0`; zero momentum is excluded. This is not a production LONG/SHORT decision and is never written to Decision Ledger.

The decision cutoff is the conceptual end of session `D`. The next observed session `D+1` is the target session. `decisionAlignedReturn = directionSign(D) * (close[D+1] / close[D] - 1)`. A positive value is target 1, a negative value is target 0, and exact zero is `EXCLUDED_FLAT`. Outcomes are usable for a later fit only once their target session is at or before that later forecast cutoff. No market sessions are inferred from calendar days.

## Model and replay rules

Model is fixed deterministic standard-library logistic regression, ID `P2_03_HISTORICAL_RESEARCH_LOGISTIC_V1`, with batch gradient descent, fixed learning rate `0.1`, L2 penalty `0.01`, and 2,500 iterations. It uses the three standardized V1 features, minimum 30 matured prior labels, and requires both target classes. No random split, alternate model, feature search, lookback search, threshold search, or repeated calibration selection is permitted. A past-only expanding base-rate forecast is the reference.

Each forecast is generated from prior matured labels only. Training labels with a target date after `D` are excluded. OOS labels are the next observed session only. Forecast provenance is exactly `HISTORICAL_RESEARCH_AS_OF_OOS`.

## Exclusions and limitations

Exclude warm-up rows, incomplete/invalid feature rows, zero research direction, missing next-session target, flat target, fewer than 30 matured prior labels, and single-class training history. No production Decision State, provider health, freshness, consistency, fallback role, production scores, or production feature contract is reconstructed.

Known limitation: the dataset has no archived per-date publication timestamps or vintages. Chronological code-level leakage controls can be audited, but source-vintage immutability and exact historical availability remain unverified. Research performance is therefore not production calibration evidence and may be interpreted only as research evidence, not as a profitability or live-trading claim.
