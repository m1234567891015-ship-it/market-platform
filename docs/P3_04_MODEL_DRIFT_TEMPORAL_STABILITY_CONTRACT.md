# P3-04 Model Drift / Temporal Stability Contract

- **Contract ID:** `P3_04_TEMPORAL_STABILITY_V1`
- **Status:** `FROZEN`
- **Authority:** Project Owner authorization for P3-04 contract, implementation, and execution.
- **Scope:** Prospective, point-in-time, immutable-ledger measurement of feature, forecast, target, realized-performance, net-expectancy, and regime-composition stability. This contract is monitoring and validation only; it does not retrain, invalidate, or replace the production model.

## 1. Frozen parent and model dependencies

- Parent: `PHASE3_MODEL_VALIDATION_V1`. Its chronology, immutability, prospective evidence identity, leakage, model, target, horizon, feature, cost, and probability-label constraints remain authoritative.
- P2-03 target: `P2_03_DIRECTIONAL_SUCCESS_V1`, non-flat decision-aligned T+1 return (`> 0` is class 1; `< 0` is class 0).
- P2-03 features: `P2_03_DERIVATIVES_SCORE_FEATURES_V1`: `marketScore`, `riskScore`, `evidenceScore`, `dataQualityScore`, each finite and within `[0,100]`.
- P2-03 model: `P2_03_LOGISTIC_REGRESSION_V1`, the existing deterministic standard-library logistic regression. P3-04 does not fit, tune, or replace it.
- P2-05 regime semantics: `P2_05_MARKET_SCORE_REGIME_V1`, LOW `[0,40)`, MID `[40,60)`, HIGH `[60,100]`; use the existing P2-05 classifier and persisted decision-time `marketScore` only.
- P3-01 owns prospective forecast replay, OOS pair eligibility, and probability chronology. P3-04 reuses its accepted fold statuses and never treats a score, scenario weight, missing value, or synthetic fixture as a probability.
- P3-03 owns canonical directional Outcome and P0B cost qualification. P3-04 reuses its eligible and cost-qualified row decisions; it does not recalculate costs or alter net-return semantics.
- Brier uses `derivatives.calibration.calculate_brier_score`. ROC AUC reuses the pure rank-statistic helper `scripts.p203_v2_historical_development._roc_auc` (helper source SHA-256 `2637c9c3a7768eabb116219472866ac67190b0b8b462015c95fc63357044e078`). P3-04 supplies only its own replay-verified prospective pairs to this helper. No historical research datasets, replays, or metrics are evidence for P3-04.
- Frozen implementation identities at contract freeze: `derivatives/probability_forecast.py` SHA-256 `52ac6f8ca6066893d4e7e959069c6cdc0481c31c8ea696690d4c8ea111487a09`; `derivatives/calibration.py` SHA-256 `8a9908ea56d91aa75198c5f9b15a1e0c95ea173ebc04c4b3c0e530d29a5490d4`; P3-01 `derivatives/walk_forward_validation.py` SHA-256 `971f68d5b342384a5f4c74b9f0f0c398f54375ebd8c71c3d3f938c435081e3ed`; P3-02 `derivatives/regime_conditioned_validation.py` SHA-256 `07cba886378f7caee6328a3c059e9f6b3e8ed02ad46d4970668e3862f0dae8c7`; P3-03 `derivatives/net_expectancy_validation.py` SHA-256 `2eac2a24a366297581aa8c7c1310ab3b3b6aa06bd16ad558608c75765c19b4d9`; P2-05 `scripts/p205_regime_performance.py` SHA-256 `fc4e5b9dfef9b945e78ce1410c6e58cd84137578a98323e06c9ea3b9412dda7a`.

## 2. Prospective evidence and chronology

- Authoritative input is only the canonical `data/p203-prospective-ledger.sqlite3`, opened read-only. Record database SHA-256, SQLite application ID, schema fingerprint, `integrity_check`, row counts, and WAL/SHM fingerprints before and after analysis.
- Each row remains its original immutable Decision or separately persisted Outcome. No backfill, reconstruction, synthetic authoritative observation, future feature, or inferred association is allowed.
- All populations are ordered by timezone-aware Decision timestamp ascending, with stable Decision ID as the tie-break. No randomization or shuffling is allowed. A label is available only after its Outcome evaluation time is strictly later than its Decision time; P3-01 additionally requires each training label's evaluation time to precede the held-out Decision.
- Each temporal evidence population is windowed independently; a Decision, forecast, target, OOS pair, or cost-qualified Outcome cannot be borrowed from another population to fill a window.
- Synthetic inputs are marked `SYNTHETIC_TEST_ONLY` and may establish pipeline behavior only. They never contribute to authoritative counts, metrics, report fingerprints, or maturity.

## 3. Frozen temporal windowing

- `WINDOW_SIZE = 30` observations per block. This P3-04 monitoring block is separate from P3-01's expanding training window and does not change any P2-03/P3-01 sample gate.
- In each independently eligible population, the immutable reference is the first 30 observations. The first comparison window is the next 30. Additional current windows are subsequent, non-overlapping chronological blocks of 30, each compared with the same first-30 reference.
- Only complete 30-observation blocks are compared. Incomplete tail rows remain counted as eligible but are not included in a comparison.
- Fewer than 60 eligible observations means `NOT AVAILABLE — INSUFFICIENT TEMPORAL OBSERVATIONS`; do not emit a numeric comparison or synthetic drift value.
- Reference observations are never redefined using later data. The block is a deterministic descriptive monitoring unit, not a fitted or optimized threshold.

## 4. Input feature stability

- Population: unique persisted Decisions with a valid timezone-aware Decision timestamp and a complete P2-03 feature vector accepted by the existing `build_feature_vector` point-in-time checks. The P2-03 feature values must be finite numeric values in `[0,100]`; missing, boolean, malformed, nonfinite, out-of-range, or future-as-of inputs are excluded and counted by reason. An Outcome is not required for this population.
- For each feature and each complete window report `n`, mean, median, population standard deviation, minimum, and maximum. For every current block versus the fixed reference report mean, median, and population-standard-deviation deltas.
- Use the frozen score bins `[0,10)`, `[10,20)`, `[20,30)`, `[30,40)`, `[40,50)`, `[50,60)`, `[60,70)`, `[70,80)`, `[80,90)`, `[90,100]`. Value 100 belongs to the last bin.
- Report per-window counts and proportions for LOW/MID/HIGH regime composition using the existing P2-05 classifier over the same feature-eligible rows. Invalid `marketScore` remains excluded from regime proportions and is separately counted; do not recompute or amend regime boundaries.

## 5. PSI definition and zero-bin handling

- Use deterministic Population Stability Index (PSI) for each score feature and for valid model forecast probabilities.
- Feature bins are the ten frozen score bins above. Forecast bins are `[0.0,0.1)`, `[0.1,0.2)`, …, `[0.8,0.9)`, `[0.9,1.0]`; probability 1 belongs to the final bin.
- For a window with `K` bins and counts `c_i`, use fixed additive pseudo-count `epsilon = 0.000001` per bin and smoothed proportions `p_i = (c_i + epsilon) / (n + K * epsilon)`. This gives every bin a finite positive proportion, including empty bins.
- With reference proportions `P_i` and current proportions `Q_i`, `PSI = sum((Q_i - P_i) * ln(Q_i / P_i))`. Report finite PSI only when both windows are complete and valid. Identical counts must yield zero within floating-point tolerance.
- PSI is numeric descriptive evidence only. Drift severity is `NOT GOVERNANCE-CLASSIFIED`; no alert, pass/fail, model invalidation, retraining, or replacement threshold is defined.

## 6. Forecast, target, and performance stability

- Forecast-output population: only Decisions whose persisted probability forecast is replay-verified by P3-01 against the frozen model and whose decision/training provenance is accepted. The forecast identity, target, feature, model, horizon, generated time, fit cutoff, finite `[0,1]` value, and prospective provenance must be valid. Missing probabilities are omitted, never replaced. Report valid forecast count, mean, median, population standard deviation, minimum, maximum, fixed-bin proportions, and reference-versus-current probability PSI when complete windows exist.
- Matured target population: only P3-03-eligible canonical evaluated directional T+1 Outcomes for explicit eligible LONG/SHORT Decisions, further requiring a non-flat P2-03 target from `derive_directional_target`. Report positive/negative counts and positive rate per window, then current-minus-reference rate. `NO_TRADE`, `HOLD_EXISTING`, invalid associations, non-EVALUATED rows, incompatible basis, invalid chronology, and flat labels are excluded.
- Brier/AUC population: only P3-01 `VALID_PROSPECTIVE_OOS_PAIR` rows, which require a replay-verified prospective forecast and eligible matured target. Use exactly 30 chronological pairs per window. Brier is calculated independently per window with the existing calibration primitive; report current-minus-reference Brier. AUC is calculated independently per window with the frozen reused rank helper only when both target classes occur. A single-class window reports `NOT AVAILABLE — SINGLE CLASS`; there is no fallback. Do not infer probability calibration or promote `probabilityLabelAllowed`.
- Net-expectancy population: only the row keys marked `INCLUDED_NET_EXPECTANCY` by P3-03, separately for each instrument, P0B cost-contract version, and currency. Use persisted P3-03-qualified `net_return` values only. For each scope, report reference mean, current-block mean, and current-minus-reference delta only when each window contains 30 qualified observations. No cross-instrument/currency pooling or cost recalculation is permitted.
- No performance metric is calculated from `NO_TRADE`, non-EVALUATED, invalid-basis, immature, non-finite, or otherwise ineligible observations. Missing inputs produce `null` / `NOT AVAILABLE`, never zero.

## 7. Report, claims, and governance boundary

- Report input counts, exclusion counts, evidence class, population-specific windows, metrics and availability reasons, dependencies, deterministic input fingerprint, and report fingerprint. Canonical JSON is UTF-8, sorted keys, compact separators, and rejects NaN/Infinity.
- Pipeline readiness is separate from authoritative evidence availability. An empty sample may be `ENGINEERING: PASS` and `TEMPORAL-STABILITY PIPELINE: READY` while authoritative metrics are `NOT AVAILABLE — INSUFFICIENT TEMPORAL OBSERVATIONS`.
- There is no single overall drift score or model-health percentage. Do not invent PSI, Brier, AUC, base-rate, or expectancy severity thresholds. Report `DRIFT SEVERITY: NOT GOVERNANCE-CLASSIFIED`.
- P3-04 V1 makes no automatic decision to invalidate a model, retrain, replace a model, select features, tune thresholds, or change production behavior. It makes no claim that drift is present or absent, nor any claim of predictive validity, profitability, alpha, trading edge, statistical significance, probability calibration, or probability-label approval.
- The P3-04 engineering execution does not formally accept/close P3-04, formally close Phase 3, or authorize Phase 4. Formal acceptance requires a separate Project Owner decision.
