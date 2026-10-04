# P3-02 Regime-Conditioned Validation Contract

**Contract ID:** `P3_02_REGIME_CONDITIONED_VALIDATION_V1`  
**Status:** `FROZEN`  
**Scope:** P3-02 validation layer over the frozen P2-03 model and P2-05 regime contract.  
**Authority:** Project Owner P3-02 authorization following formal P3-01 closure.

## 1. Frozen dependencies

- Phase 3 baseline: `PHASE3_MODEL_VALIDATION_V1`, SHA-256 `43ebcad66cd8267c07bca2419fbbcdeca066e6195eecf1e4ac782fd5954bbc57`.
- Regime semantics: `P2_05_MARKET_SCORE_REGIME_V1`, SHA-256 `e65588e9c771a06b6ee51bccefa0351033420824e77969092a875ac03edd11d2`.
- Forecast target: `P2_03_DIRECTIONAL_SUCCESS_V1`, T+1 observed market session.
- Features: `P2_03_DERIVATIVES_SCORE_FEATURES_V1`.
- Model: `P2_03_LOGISTIC_REGRESSION_V1`, evaluated through the frozen P3-01 deterministic walk-forward pipeline.

These dependencies are inputs to P3-02. P3-02 does not alter or reopen them.

## 2. Population and regime assignment

- Use only the canonical prospective Decision Ledger cohort read by P3-01 and its separate T+1 Outcomes.
- Assign a held-out Decision to exactly one regime using the existing P2-05 `decision_regime` / `classify_market_score` primitives and only the immutable `decision_output_json.marketScore` snapshot.
- Preserve the P2-05 boundaries: LOW `[0,40)`, MID `[40,60)`, HIGH `[60,100]`.
- Missing, nonnumeric, boolean, nonfinite, or out-of-range scores are `REGIME_INVALID`, remain visible in coverage, and are excluded from regime metrics. Never impute or recompute scores.
- Regime is a reporting partition over the unchanged global P2-03 model's held-out evidence. It does not create a regime-specific model, refit by regime, alter feature selection, or change the P3-01 expanding training set. P3-01 strict chronology, matured-label purge, prospective identity, replay, and provenance checks remain authoritative.

## 3. Eligibility and evidence separation

- Report separately: immutable decision coverage by regime; P2-05-eligible evaluated directional T+1 Outcomes; P2-03-eligible non-flat target observations; replay-verified persisted forecast count; and valid prospective P3-01 OOS pair count.
- P2-03 target eligibility remains governed by `derive_directional_target`; flat returns are excluded from the binary target. `NO_TRADE`, `HOLD_EXISTING`, unknown/mismatched direction, non-true `decisionEligible`, invalid regime, invalid association, invalid chronology, incomplete provenance, and non-evaluated or incompatible Outcomes fail closed.
- Only OOS pairs accepted by P3-01 and also accepted by P2-05's T+1 association/eligibility audit contribute to paired regime metrics. Each pair belongs to one regime only.
- Synthetic fixtures may exercise mechanics but are always `SYNTHETIC_TEST_ONLY`; they never contribute to the authoritative evidence count or maturity result.

## 4. Minimal regime-conditioned report

Emit one deterministic row for each of LOW, MID, and HIGH, including zero-evidence rows for pipeline visibility. Each row reports:

- decision count;
- eligible evaluated directional Outcome count;
- eligible non-flat target count and positive / negative target counts;
- replay-verified persisted forecast count;
- valid prospective OOS pair count and positive / negative paired target counts;
- mean forecast, realized positive rate, and Brier score computed only from that regime's valid OOS pairs (otherwise `null`);
- Brier Skill Score as `null` / not calculated because no same-contract frozen prospective reference is defined;
- mean `decisionAlignedReturn` only from valid OOS pairs with eligible authoritative P2-02 Outcome semantics (otherwise `null`);
- net return as `null` / not calculated; P3-03 owns net expectancy and its frozen cost semantics;
- sample sufficiency status and evidence class.

Reuse `derivatives.calibration.calculate_brier_score`; do not introduce alternate calibration metrics. Brier and descriptive return fields do not imply calibration, model approval, profitability, or a trading edge. `probabilityLabelAllowed` remains `false`.

## 5. Sample sufficiency and maturity

- Reuse the frozen P2-03 / P3-01 gate without adding a new threshold: a regime's valid prospective OOS evidence is mature only at 30 or more pairs and with both target classes present.
- A regime with zero pairs reports `NOT AVAILABLE — NO VALID PROSPECTIVE OOS PAIRS`. A nonempty regime below the gate or missing a target class reports `INSUFFICIENT_SAMPLE`. A regime meeting the gate reports `MATURE_PENDING_OWNER_ADJUDICATION`.
- Overall authoritative regime evidence is mature only when at least one regime has valid pairs and every regime with valid pairs meets the same 30-pair / both-class gate. This remains pending Project Owner adjudication and is not a statistical-significance test.
- Pipeline readiness and statistical maturity are independent. Empty authoritative evidence may yield `VALIDATION PIPELINE READY` while realized regime statistics remain `NOT AVAILABLE` and maturity remains `NOT YET MATURE`.

## 6. Integrity, reproducibility, and boundaries

- Authoritative access is read-only and pinned to `data/p203-prospective-ledger.sqlite3`.
- Before and after analysis, record main DB SHA-256, Decision and Outcome counts, schema fingerprint, SQLite `integrity_check`, eligible directional Outcome count, and DB/WAL/SHM fingerprints. Any change or failed integrity check blocks the report.
- Canonical report serialization is deterministic. Two independent authoritative runs must produce identical report fingerprints when the DB and frozen dependencies are unchanged.
- Chronology and leakage checks are inherited from P3-01; actual chronology is `NOT OBSERVED` when there are no valid pairs. Regime assignment uses no Outcome, forecast, or future value.
- P3-02 makes no claims of predictive validity, statistical significance, regime monotonicity, profitability, alpha, trading edge, calibration success, or probability-label promotion.
- This contract does not authorize P3-03, P3-04, Phase 4, production-model replacement, probability-label promotion, DB writes, Git promotion, or deployment.
