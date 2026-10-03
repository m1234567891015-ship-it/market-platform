# Phase 3 Model Validation Contract

**Contract ID:** `PHASE3_MODEL_VALIDATION_V1`  
**Status:** `FROZEN`  
**Authority:** Project Owner Phase 3 authorization  
**Scope:** P3-01 through P3-04 in the fixed order below; only P3-01 is authorized for execution now.

## 1. Phase 3 sequence

1. `P3-01 — Walk-Forward Validation`
2. `P3-02 — Regime-Conditioned Validation`
3. `P3-03 — Net Expectancy Validation`
4. `P3-04 — Model Drift / Temporal Stability`
5. Phase 3 Formal Closure

This sequence follows the investment-decision audit: Walk-Forward → Regime-conditioned Backtest → Net Expectancy → Model Drift. It does not authorize execution of P3-02 or later work.

## 2. Frozen P2-03 baseline

P3 validates, and does not modify, this baseline:

- Target: `P2_03_DIRECTIONAL_SUCCESS_V1` (`DIRECTIONAL_SUCCESS`); eligible LONG/SHORT decision-aligned return greater than zero is class 1, less than zero is class 0, and a flat return is excluded.
- Horizon: `T+1`, the next observed market session.
- Features: `P2_03_DERIVATIVES_SCORE_FEATURES_V1` (`marketScore`, `riskScore`, `evidenceScore`, `dataQualityScore`).
- Model: `P2_03_LOGISTIC_REGRESSION_V1`, deterministic standard-library logistic regression with its existing fixed optimizer parameters.
- Training gate: at least 30 eligible, matured prior labels and both target classes. Insufficient or single-class history fails closed.
- Probability-label policy: `probabilityLabelAllowed=false`; validation does not promote probability labels.

P3 may not alter target, horizon, features, model, thresholds, sample windows, P2-05 regime boundaries, production decisions, costs, or P2 contracts to improve validation results.

## 3. Cross-phase invariants

- Decisions are immutable; Outcomes remain separate records.
- Only point-in-time decision inputs may be used. A fit cutoff and every training label's evaluation time must precede the held-out decision time.
- No shuffled split, future feature, future Outcome, backfill, synthetic authoritative record, or cross-instrument training is allowed.
- Only records with the frozen prospective forecast identity can count as prospective model evidence. Historical research replay results remain research-only and are not independent prospective validation.
- `Score != Probability`; `Scenario Weight != Probability`.
- Cold start remains fail-closed. Unknown or invalid evidence is excluded, not imputed.
- Existing transaction-cost semantics are not changed. P3-01 evaluates the frozen binary directional target only; it does not assert net expectancy or trading profitability.

## 4. P3-01 walk-forward fold contract

- Population: immutable prospective Decision Ledger records and their separately stored `T+1` Outcomes for the same frozen instrument/model cohort.
- Ordering: strict ascending decision time, with stable decision ID tie-break. No randomization.
- Fold: one eligible LONG/SHORT decision is the single holdout observation for that fold.
- Training window: expanding. For a held-out decision, use the existing P2-03 deterministic fitter and all eligible same-instrument P2-02 `EVALUATED` labels whose decision time and outcome evaluation time are strictly earlier than the held-out decision time. Do not drop older eligible rows or introduce a new lookback.
- Purge/embargo: the strict matured-outcome cutoff above purges any label not fully observed before the held-out decision. No additional calendar-day embargo is introduced; T+1 remains an observed-session horizon.
- Forecast identity: the ledger must contain a persisted forecast with the frozen target, feature, model, horizon, prospective provenance, and a fit cutoff earlier than the held-out decision. Recompute that fold with the existing fitter and require deterministic forecast agreement. The held-out Outcome must pass the existing `valid_oos_pair` contract and be evaluated after the decision.
- Ordering protection: each fold's forecast is verified before its own Outcome is admitted to evaluation. A prior fold's label may enter a later fold only after its Outcome has matured before that later decision. Fold results may not tune, select, or replace the frozen model.
- Metrics: reuse existing out-of-sample calibration primitives; do not define duplicate metrics. Metric output is descriptive. It does not imply model acceptance, calibration, profitability, probability-label approval, or production promotion.
- Statistical evidence maturity: at least 30 eligible prospective walk-forward forecast/Outcome pairs and both held-out target classes are required before reporting the evidence as mature. This reuses the frozen P2 minimum and class-variation gate; it is not a new tuning threshold. Until then, report `STATISTICAL VALIDATION EVIDENCE NOT YET MATURE` even when the pipeline is ready.
- Empty/cold-start data is a valid pipeline result: `VALIDATION PIPELINE READY` may coexist with `STATISTICAL VALIDATION EVIDENCE NOT YET MATURE`.

## 5. P3-01 acceptance and boundaries

P3-01 engineering/pipeline readiness requires deterministic read-only loading, explicit fold eligibility and exclusion counts, chronology and leakage checks, reproducible output, isolated regression coverage, and unchanged authoritative database integrity. Synthetic fixtures may test those mechanics only and must be labeled test-only.

P3-01 does not claim statistical validation until the maturity gate is met. Even after maturity, this contract alone does not create a statistical performance PASS threshold; Project Owner adjudication is required. P3-01 completion does not close Phase 3 or authorize P3-02, P3-03, P3-04, Phase 4, probability-label promotion, or Git promotion.

