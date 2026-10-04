# P2-03 Historical Research V2 Pre-Registration

**Protocol status:** `PRE-REGISTERED — AWAITING OWNER AUTHORIZATION`  
**Execution status:** `NOT AUTHORIZED / NOT STARTED`  
**Classification:** `RESEARCH_ONLY / NOT_PRODUCTION / NOT_LIVE_PROSPECTIVE / NOT_P2_03_DERIVATIVES_SCORE_FEATURES_V1`

This document freezes a proposed V2 research protocol before any V2 feature matrix, model fit, forecast, replay, backtest, or performance metric is generated. It is a design and pre-registration record only. The protocol document hash is recorded in `.tmp/p203-v2-protocol/protocol_manifest.json`; the manifest does not hash itself.

## 1. Research question and hypothesis

**Research question:** Does the one pre-registered set of no more than six economically interpretable, structurally point-in-time-safe TX features produce more stable discrimination and more useful probability information than a past-only expanding base-rate forecast in a prospective chronological evaluation?

**Primary hypothesis:** On the first 272 valid, prospectively captured, chronological V2 forecast/outcome pairs after a separate prospective training seed, the fixed V2 logistic model will have a lower Brier score than the past-only naive base-rate forecast and discrimination above chance, with uncertainty intervals that support both comparisons.

This is a research hypothesis, not a production claim. It will be considered unsupported or inconclusive if the pre-registered evaluation rules below are not met. The known V1R1 findings motivate asking whether stable incremental signal exists; no feature below was selected by searching V1R1 feature quintiles, largest-error dates, best-performing quarters, or coefficient signs.

## 2. Known V1R1 evidence

V1R1 contains 272 historical research OOS pairs. Its known results are AUC `0.48723`, accuracy at 0.5 `0.50`, model Brier `0.2588409524` versus naive `0.2532434161`, Brier Skill Score `-0.02210338`, and model ECE `0.0595347228` versus naive `0.0300935998`. The V1R1 diagnostic also observed coefficient sign changes, variation in training base rates, and a `NOT PROVEN` historical source vintage. Its formal interpretation remains `EVIDENCE INCONCLUSIVE`.

These results are context only. V1R1 remains unchanged and is not the promotion baseline. The core reference for V2 is the past-only naive forecast on the same V2 evaluation observations.

## 3. Proposed identifiers and scope

| Field | Proposed value |
|---|---|
| Feature contract | `P2_03_HISTORICAL_RESEARCH_FEATURES_V2` |
| Model | `P2_03_HISTORICAL_RESEARCH_LOGISTIC_V2` |
| Evidence class | `HISTORICAL_RESEARCH_AS_OF_OOS` for development only; `PROSPECTIVE_RESEARCH_OOS` for the final window |
| Data | TAIFEX TX daily observations, highest-volume eligible contract selected per market date |
| Production relationship | None; must not be wired into production or `P2_03_DERIVATIVES_SCORE_FEATURES_V1` |

Identifiers are proposed names only. They do not authorize implementation.

## 4. Proposed feature contract

The feature cap is **six total features**. All feature values are calculated after the close of session D from fields available by the forecast cutoff. The proposed direction anchor and target retain the V1 research meaning. Features are hypotheses selected from market rationale and field availability, not from post-hoc V1R1 outcome diagnostics.

Definitions use the daily highest-volume selected TX contract series. `sign5(D) = sign(close[D] / close[D-5] - 1)`. Any zero sign is excluded under the frozen direction rule.

| Name | Formula | Lookback | Required fields | Economic rationale / expected relationship |
|---|---|---:|---|---|
| `momentum_strength_5` | `abs(close[D] / close[D-5] - 1)` | 5 sessions | close | Magnitude of the same five-session impulse that defines direction; pre-registered expected relationship: positive with next-session success if directional persistence exists. |
| `range_pct_1` | `(high[D] - low[D]) / close[D]` | 0 prior sessions | high, low, close | One-session realized range; expected negative relationship, as a wider single-session range may reflect noisier directional follow-through. |
| `trend_alignment_20` | `sign5(D) * (close[D] / close[D-20] - 1)` | 20 sessions | close | Tests whether the five-session direction aligns with a fixed approximately one-month trend; expected positive relationship. The 20-session horizon is fixed once and is not a search grid. |
| `volume_confirmation_5` | `sign5(D) * (close[D] / close[D-1] - 1) * (volume[D] / mean(volume[D-5..D-1]) - 1)` | 5 sessions | close, volume | Measures a direction-aligned daily move with current volume expansion over the preceding five sessions; expected positive relationship if participation confirms follow-through. |
| `directional_price_location_20` | `sign5(D) * (2 * (close[D] - min(low[D-19..D])) / (max(high[D-19..D]) - min(low[D-19..D])) - 1)` | 19 sessions | close, high, low | Measures whether current close location within the fixed 20-session range agrees with the five-session direction; expected positive relationship. Zero range is invalid. |
| `range_pct_5` | `(max(high[D-4..D]) - min(low[D-4..D])) / close[D]` | 4 prior sessions | high, low, close | Five-session realized range; expected negative relationship if a wider recent range reflects less predictable next-session directional follow-through. |

The expected relationships are hypotheses, not constraints imposed on fitted coefficients. They will not be changed after V2 results are observed. Open interest is omitted because aggregate open interest does not identify whether new positions are long or short; assigning it a directional sign would require an additional unsupported interpretation. No feature interactions, polynomial expansion, indicator search, alternative lookbacks, or quality-score proxies are authorized.

### Point-in-time and roll rules

- Decision cutoff is end-of-session D only after required daily fields have actually been received. For any prospective evaluation row, the captured input payload and receive time must precede the forecast record; missing or late data fail closed.
- TAIFEX historical publication timing, historical vintages, and revision history remain `NOT PROVEN`. Structural as-of formulas do not prove that a retrospectively downloaded historical value was available on D. Historical development is therefore exploratory and cannot establish final PIT evidence.
- Retain the existing daily selection rule: highest-volume eligible TX contract per date; equal-volume ties retain the first eligible row in source order. Record the raw response, selection trace, and hashes.
- No synthetic, back-adjusted, ratio-adjusted, or Panama continuous series is allowed.
- A forecast row is roll-clean only when every selected daily observation in the union of the longest feature lookback and the target boundary—sessions D-20 through D+1—has the same `contractMonth`. Any contract transition in that window excludes the row. No roll adjustment is applied.
- Missing fields, non-positive denominators, invalid ranges, absent lookback rows, zero direction, flat target, or failed continuity exclude the row. No imputation is permitted.

## 5. Direction, target, and training

Preserve the V1 research direction semantic:

- `RESEARCH_LONG` when `close[D] / close[D-5] - 1 > 0`.
- `RESEARCH_SHORT` when it is below zero.
- Zero momentum is excluded.

Preserve the V1 target and horizon:

```text
target = 1 if sign5(D) * (close[D+1] / close[D] - 1) > 0
target = 0 if sign5(D) * (close[D+1] / close[D] - 1) < 0
flat target = excluded
horizon = T+1 observed market session
```

The target and direction are research-only; this does not define a trading recommendation or realized net profit.

Use chronological expanding training with only prior matured, eligible, roll-clean labels whose target date and source availability precede the forecast cutoff. Require at least 30 prior matured labels and both classes. If either condition fails, emit no forecast. The model may expand using subsequently matured prior labels, but no future row or future base rate may enter a forecast.

## 6. Model, normalization, and naive reference

Freeze the model family to deterministic standard-library logistic regression. Keep the V1 algorithm and settings unchanged: 2,500 iterations, learning rate `0.1`, L2 penalty `0.01`, zero initialization, the existing stable sigmoid, and the existing stopping/weight update implementation. The only intended modeling-contract change is the six pre-registered feature definitions. No regularization search, alternative model family, calibration layer, threshold tuning, or hyperparameter tuning is authorized.

For each forecast, fit feature means and population standard deviations from that forecast's eligible prior training rows only. A zero standard deviation maps that feature to zero as in V1. Full-sample normalization is forbidden.

The naive forecast is the expanding positive-label rate computed from exactly the same eligible, matured, prior training rows available to the V2 forecast. No future or full-sample base rate may be used.

## 7. Data windows and untouched evaluation

### Development window

Proposed historical development window: `2024-12-06` through `2026-10-01`, inclusive. Existing inventory contains 441 selected TX sessions, 326 V1R1 roll-clean feature rows, 303 clean matured labels, and 272 V1R1 OOS pairs. The exact V2 eligible count is **not calculated** in this design-only round; the 20-session roll rule and additional fields may reduce it. This window is development-only, already exposed to V1/V1R1 analyses, and has unproven source vintages. It may be used after separate implementation authorization to check code paths and produce development research metrics, but never to claim untouched or independent evaluation.

Development execution is one frozen run. No result-driven feature revision, model revision, or repeated selection is allowed. A poor result remains the V2 development result; any later research contract requires a distinct owner authorization and a new pre-registration before its outcomes are examined.

### Historical final evaluation feasibility

The existing historical source ends on `2026-10-01`. All available dates through that boundary have been used in V1/V1R1 replay or the V1R1 diagnostic, including feature, coefficient, quarter, rolling, and error analyses. Therefore:

```text
HISTORICAL FINAL TEST: NOT PRISTINE
INDEPENDENT HISTORICAL FINAL EVALUATION: NOT AVAILABLE
```

No earlier slice of this viewed history may be relabeled as untouched. No synthetic future observations may be created.

### Prospective seed and final window

- **Prospective training seed:** after separate V2 implementation authorization and source-provenance readiness, collect prospectively captured, eligible, roll-clean T+1 examples until there are at least 30 matured labels and both classes. These seed observations are training-only and are excluded from the final metric sample.
- **Final evaluation window:** the next **272 consecutive eligible, roll-clean, prospectively forecast and matured outcome pairs** after the seed gate. Start date is future and not currently available. Preserve every eligible pair; apply only the fixed missing-data, flat-target, and roll exclusions above. Do not inspect aggregate final performance until all 272 pairs and their hashes are frozen. No optional stopping or outlier removal.
- Current prospective ledger state is `decision_ledger=1`, `decision_outcome=0`; the existing row is ineligible for this V2 protocol and has no complete normalized provenance. Current valid prospective seed/final capacity is therefore **0 / 0**.
- Historical V1R1 generated 272 pairs from 441 selected sessions (61.68%). At that rate, 30 seed plus 272 final pairs would require approximately 490 selected sessions. This is a rough capacity analogue only; V2's stricter 20-session continuity rule can lower eligibility, and prospective availability is unknown. The sample size does not have a completed power analysis; meaningful power is `NOT ESTABLISHED`.

Final-window integrity requires that its dates are strictly after the frozen protocol and implementation, that no final outcomes are used for feature/model design or normalization, and that the final 272 pairs are not inspected until the sample is complete. The V1R1 set is not a pristine test. A V1R1 comparison may be shown only as a historical reference; naive remains the primary comparator.

## 8. Metrics and uncertainty

Freeze metrics before V2 execution:

**Primary:**

1. Brier score.
2. Brier Skill Score versus the same-observation past-only naive base rate, `1 - modelBrier / naiveBrier`.
3. ROC AUC, clearly labeled discrimination rather than calibration.

**Secondary diagnostics:**

- ECE with exactly 10 equal-width bins `[0.0,0.1) ... [0.9,1.0]`; no result-driven bin changes.
- Forecast distribution, calibration bins, base rate at each forecast and realized target rate.
- Coefficient trace, coefficient sign transitions, coefficient magnitude trace.
- Quarterly performance on fixed calendar quarters, 20-observation rolling Brier and expanding cumulative Brier.
- Top-10/top-20 Brier-loss contributions; retain all rows and never remove extremes.
- Brier reliability/resolution/uncertainty decomposition as a binned descriptive diagnostic, with the binning limitation disclosed.

**Proposed uncertainty analysis (not yet executed):** standard-library paired circular moving-block bootstrap on the chronological final pairs, block length 20 observations (the frozen maximum feature lookback), 10,000 replicates, fixed PRNG seed `2030301`, percentile 95% intervals for paired model-minus-naive Brier difference and AUC. Report invalid single-class AUC replicates and do not replace them silently. The effective number of 20-observation blocks in 272 pairs is small; interval precision and statistical power may be poor. The Owner must adjudicate this proposed interval method before V2 execution. No large dependency is proposed.

If the Owner does not approve an uncertainty method before execution, interval-dependent classification is `NOT AVAILABLE` and the result must be `RESEARCH RESULT INCONCLUSIVE`.

## 9. Proposed research continuation rule (not production promotion)

This candidate rule is for deciding whether a later, separately authorized research replication is justified. It cannot approve a production model.

- `RESEARCH SIGNAL SUPPORTED` only if all 272 final pairs pass data/PIT/roll integrity, the paired 95% interval for model-minus-naive Brier lies entirely below zero, and the 95% AUC interval lies entirely above the no-discrimination value `0.5`.
- `RESEARCH SIGNAL NOT SUPPORTED` if the complete valid final evaluation has the paired Brier interval entirely at or above zero and the AUC interval entirely at or below `0.5`.
- `RESEARCH RESULT INCONCLUSIVE` for mixed intervals, insufficient/missing pairs, invalid required metrics, unresolved provenance/roll integrity, or unavailable uncertainty intervals.

These are proposed research-only relational rules using the naive equality boundary and chance AUC boundary; they do not set an absolute Brier target and require Project Owner adjudication before execution. ECE and coefficient stability remain secondary diagnostics and do not independently trigger model promotion. `P2-03` production remains blocked until its separate prospective calibration gate is satisfied and formally adjudicated.

## 10. Reproducibility and freeze requirements

Any separately authorized V2 implementation/evaluation must record SHA-256 for: raw input responses, frozen contract, daily selection trace, feature matrix, per-forecast training trace, forecast file, OOS pair file, and metrics report. Store exact source timestamps, selected contract month, target maturity, exclusion reason, and model/version identifiers. Verify deterministic reruns byte-for-byte where the environment allows. Compare the protocol document hash against the manifest before implementation; any change requires a new version and owner authorization before results are seen.

## 11. Forbidden actions

This protocol does not authorize V2 implementation or execution, a V2 feature matrix, model fitting, forecasts, replay/backtest, or V2 performance calculation. It does not authorize changes to V1/V1R1 artifacts, the prospective database, production scoring, `probabilityLabelAllowed`, P2-03 closure, P2-04/P2-05/P3/P4, Git promotion, or deployment. It does not authorize Random Forest, XGBoost, neural networks, SVM, AutoML, feature grids, lookback grids, interaction search, imputation, recalibration, or repeated result-driven design.

## 12. Source limitations and formal status

The following remain explicit:

```text
Historical publication timing: NOT PROVEN
Historical vintage: NOT PROVEN
Revision history: NOT PROVEN
Historical final evaluation: NOT PRISTINE / NOT AVAILABLE
Prospective final evaluation: NOT STARTED / 0 valid pairs
V2 implementation: NOT AUTHORIZED / NOT STARTED
probabilityLabelAllowed: false
Production P2-03: BLOCKED — INSUFFICIENT PROSPECTIVE OOS CALIBRATION HISTORY
```

**Protocol status:** `PRE-REGISTERED — AWAITING OWNER AUTHORIZATION`  
**V2 implementation:** `NOT AUTHORIZED / NOT STARTED`  
**Protocol SHA-256:** recorded in `.tmp/p203-v2-protocol/protocol_manifest.json` and canonical execution status.  
**Created:** 2026-10-02.
