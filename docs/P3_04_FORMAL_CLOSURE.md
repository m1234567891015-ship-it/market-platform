# P3-04 Model Drift / Temporal Stability — Formal Acceptance and Closure

**Date:** 2026-10-03
**Scope:** P3-04 only
**Status:** CLOSED
**Result:** PASS — ENGINEERING / GOVERNANCE CLOSURE
**Owner decision:** Approved by the Project Owner's `P3-04 — Formal Acceptance / Close` authorization.

## Frozen contract

- **Contract ID:** `P3_04_TEMPORAL_STABILITY_V1`
- **Contract file:** `docs/P3_04_MODEL_DRIFT_TEMPORAL_STABILITY_CONTRACT.md`
- **SHA-256:** `95e13031cedf996a7a6935c33b9fb01c20776f91f58d64c71b7c9af0f63e6bd6` (reconfirmed unchanged during this closure)
- **Parent contract:** `PHASE3_MODEL_VALIDATION_V1`, SHA-256 `43ebcad66cd8267c07bca2419fbbcdeca066e6195eecf1e4ac782fd5954bbc57`.

The accepted implementation monitors point-in-time feature, forecast-output, target/base-rate, paired forecast performance, net-expectancy, and regime-composition stability. It reuses the frozen P2-03 model and target, P2-05 regime semantics, P3-01 replay/chronology checks, and P3-03 eligibility and cost-qualified rows. It does not retrain, invalidate, replace, or promote a production model.

## Accepted temporal contract

- Each independent evidence population is ordered by timezone-aware Decision time ascending, with stable Decision ID tie-break; no shuffle, future-to-past leakage, or cross-population borrowing is allowed.
- `WINDOW_SIZE = 30`: the first 30 eligible observations are the fixed reference; subsequent non-overlapping chronological blocks of 30 are comparison windows. A comparison requires at least 60 eligible observations. Incomplete tails are not used to fill a window.
- Eligible features remain `marketScore`, `riskScore`, `evidenceScore`, and `dataQualityScore`, with the frozen ten fixed score bins from `[0,10)` through `[90,100]`.
- PSI remains descriptive only, using frozen `epsilon = 0.000001` per bin. No severity threshold, composite drift score, alert, invalidation, retraining, or promotion rule is defined.
- Feature-input stability, forecast-output stability, and realized-performance stability remain separate evidence layers.
- Forecasts must be replay-verified prospective probabilities; missing forecasts are omitted. Matured outcomes must satisfy P3-03 eligibility. Synthetic fixtures remain test-only and never count as authoritative evidence.
- `probabilityLabelAllowed` remains `false`.

## Accepted execution and integrity evidence

Prior completed P3-04 execution evidence accepted for this closure:

- P3-04-specific regression: **17 / 17 PASS**.
- Scoped dependency regression: **131 PASS**.
- Python compile: **PASS**.
- `git diff --check`: **PASS** in the completed execution.
- Two independent analyzer processes produced report fingerprint `0cfaa6aa5794b5b3dbabdf4b0877bad857ccc28d7c6b87d4751a3b0c84c8ee5b`.

This formal-closure audit did not rerun the regression suite or compilation. It did verify the frozen contract and dependency identities, confirmed both accepted P3-04 fixes remain present, and ran the read-only authoritative analyzer. Its report fingerprint matched the accepted fingerprint above. Current source fingerprints observed during closure are `derivatives/model_drift_validation.py` SHA-256 `a7b76217efa6dcc253bd020057b1c635260546081ea5509561b8aa8b7182ee3f` and `regression/test_p304_model_drift_validation.py` SHA-256 `601a1998af426fc0ad0395e75f769b34f2c6fc5ca1f8efdfdb5f4991c544d6d4`.

The two accepted P3-04 defect remediations remain present:

1. Deterministic replay mismatches are explicitly excluded and reported as `DETERMINISTIC_REPLAY_MISMATCH`.
2. Input decision and outcome rows are canonicalized before fingerprinting, so logically identical row sets do not change the report fingerprint due only to input order.

## Authoritative evidence and database integrity

The authoritative database was accessed read-only at `data/p203-prospective-ledger.sqlite3`. The analyzer reported identical before/after snapshots and `readOnly: true`, `unchanged: true`.

| Check | Closure evidence |
|---|---:|
| Database SHA-256 | `73db5d58f9cc1b2f5723ddbb86678036a6e5c67d322cf492d3b2d0f4d2f23df4` |
| SQLite application ID | `1345466419` |
| Schema SHA-256 | `ca582e7521891078d88713c794a0b998c973972b71bd92df64e8b64ef8296c52` |
| `PRAGMA integrity_check` | `ok` |
| Decisions / Outcomes | `1 / 0` |
| Valid input feature observations | `1` |
| Valid prospective model forecasts | `0` |
| Matured directional target observations | `0` |
| Valid prospective OOS pairs | `0` |
| Cost-qualified observations | `0` |
| `probabilityLabelAllowed` | `false` |

The analyzer report fingerprint on the read-only acceptance rerun was `0cfaa6aa5794b5b3dbabdf4b0877bad857ccc28d7c6b87d4751a3b0c84c8ee5b`, matching the two prior accepted runs.

## Evidence maturity and non-claims

```text
P3-04 ENGINEERING: PASS
TEMPORAL-STABILITY PIPELINE: READY
AUTHORITATIVE DRIFT EVIDENCE: NOT AVAILABLE — INSUFFICIENT TEMPORAL OBSERVATIONS
INPUT FEATURE TEMPORAL COMPARISON: NOT AVAILABLE — INSUFFICIENT TEMPORAL OBSERVATIONS
FORECAST OUTPUT TEMPORAL COMPARISON: NOT AVAILABLE — NO VALID PROSPECTIVE MODEL FORECASTS
BASE-RATE TEMPORAL COMPARISON: NOT AVAILABLE — INSUFFICIENT TEMPORAL OBSERVATIONS
BRIER / AUC TEMPORAL COMPARISON: NOT AVAILABLE — INSUFFICIENT TEMPORAL OBSERVATIONS
NET EXPECTANCY TEMPORAL COMPARISON: NOT AVAILABLE
REGIME COMPOSITION TEMPORAL COMPARISON: NOT AVAILABLE — INSUFFICIENT TEMPORAL OBSERVATIONS
DRIFT SEVERITY: NOT GOVERNANCE-CLASSIFIED
DRIFT PRESENCE: NOT ESTABLISHED
DRIFT ABSENCE: NOT ESTABLISHED
MODEL STABILITY: NOT ESTABLISHED
MODEL RETRAINING NEED: NOT ESTABLISHED
```

Unavailable metrics were not converted to zero. This closure makes no claim that drift exists or does not exist, that the model is stable, unstable, or valid, or that retraining is needed. It does not claim predictive validity, profitability, alpha, trading edge, statistical significance, probability calibration success, or probability-label approval.

## Formal status and boundary

```text
P3-04: CLOSED
RESULT: PASS — ENGINEERING / GOVERNANCE CLOSURE
P3-01: CLOSED
P3-02: CLOSED
P3-03: CLOSED
PHASE 3 FORMAL CLOSURE: NOT EXECUTED
PHASE 4: NOT AUTHORIZED / NOT STARTED
```

This record closes P3-04 only. It does not formally close Phase 3 or authorize Phase 4, model retraining/replacement, probability-label promotion, Git promotion, or deployment.
