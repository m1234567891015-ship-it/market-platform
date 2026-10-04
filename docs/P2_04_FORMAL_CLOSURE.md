# P2-04 Formal Closure — Score Bucket Performance

**Date:** 2026-10-02  
**Scope:** P2-04 only  
**Status:** CLOSED  
**Result:** PASS — ENGINEERING / GOVERNANCE CLOSURE

## Closure decision

P2-04 engineering and analytics readiness is complete. Realized performance evidence is a separate operational maturity state and remains:

```text
REALIZED PERFORMANCE EVIDENCE:
NOT AVAILABLE — NO ELIGIBLE EVALUATED OUTCOMES

POST-CLOSURE PERFORMANCE EVIDENCE:
PENDING FUTURE AUTHORITATIVE OUTCOMES
```

Closure means the existing analyzer can deterministically and safely evaluate future authoritative outcomes. It does not mean score buckets have demonstrated predictive value or that current realized performance is known.

## Authoritative data state

The sole performance input was `data/p203-prospective-ledger.sqlite3`, read using SQLite `mode=ro&immutable=1`.

| Check | Observed |
|---|---:|
| Database SHA-256 | `73db5d58f9cc1b2f5723ddbb86678036a6e5c67d322cf492d3b2d0f4d2f23df4` |
| Decisions | 1 |
| Outcomes | 0 |
| Eligible EVALUATED LONG/SHORT outcomes | 0 |
| Decision state / direction / eligibility | `NO_TRADE` / `UNAVAILABLE` / `false` |
| `probabilityLabelAllowed` | `false` |

The one decision has frozen scores `marketScore=50`, `riskScore=51`, `evidenceScore=50`, and `dataQualityScore=75`. Each score is finite and within 0–100. Every canonical Outcome status count is zero: `EVALUATED`, `PENDING`, `NOT_APPLICABLE`, `UNAVAILABLE`, and `INVALID`.

## Performance denominator

For each score observation, the analyzer requires all of the following:

- Decision state and execution direction are the same value, `LONG` or `SHORT`.
- Persisted `decisionEligible` is exactly the boolean `true`.
- The authoritative Outcome `status` column is exactly canonical `EVALUATED` and agrees with any stored status metadata.
- `evaluationBasis` is `DIRECTIONAL_RETURN` and `decisionAlignedReturn` is a finite numeric value.
- The decision-time score is a finite numeric value in the inclusive range 0–100.
- The decision and Outcome association, horizon, and uniqueness checks pass.

The analyzer excludes `NO_TRADE`, `HOLD_EXISTING`, `UNKNOWN`, false/missing/unknown/non-boolean eligibility, all non-EVALUATED statuses, incompatible bases, invalid returns, and invalid score observations. Legacy `AVAILABLE` or `PARTIAL` statuses are not upgraded to `EVALUATED`.

## Score and bucket contract

Only persisted decision-time `marketScore`, `riskScore`, `evidenceScore`, and `dataQualityScore` are used; historical decisions are not recalculated. Scores outside 0–100, missing values, booleans, non-numeric values, NaN, and infinity fail closed.

Buckets remain fixed and deterministic:

```text
[0,10) [10,20) [20,30) [30,40) [40,50)
[50,60) [60,70) [70,80) [80,90) [90,100]
```

The final interval includes 100. No adaptive or optimized thresholds were added. `riskScore` remains a risk magnitude; the analyzer does not interpret higher or lower values as better. When outcomes exist, each result contains `n`, outcome counts, directional success rate, mean and median decision-aligned return, and an explicit descriptive-only interpretation.

## Join integrity and fail-closed behavior

On the current authoritative DB: joined Decision/Outcome IDs `0`; orphan Outcomes `0`; duplicate Decision IDs `0`; duplicate Decision/horizon Outcome associations `0`; invalid Decision/Outcome metadata relationships `0`; status metadata mismatches `0`; incompatible status/basis pairs `0`.

Regression fixtures also exercise non-zero orphan and duplicate joins, metadata Decision ID and horizon mismatches, status metadata conflicts, incompatible status/basis pairs, and noncanonical statuses. Such rows are reported and excluded. Zero eligible outcomes produce only structured inventory, contract, funnel, integrity, determinism, and blocker artifacts. No empty performance CSV, zero-percent success rate, or synthetic performance is emitted.

## Verification and determinism

The synthetic acceptance matrix covers positive and negative directional returns for LONG and SHORT; `NO_TRADE`, `HOLD_EXISTING`, and `UNKNOWN`; eligibility false, missing, unknown, and non-boolean; every non-EVALUATED status; score boundaries including 0, 9.999999, 10, 99.999999, and 100; invalid and out-of-range scores; orphan and duplicate associations; incompatible basis and mismatched metadata; and zero-evidence output behavior. Fixtures are test evidence only and were never inserted into the authoritative DB.

The final analyzer was run twice against the same DB. Both runs classified the result as `BLOCKED — NO ELIGIBLE EVALUATED OUTCOMES`, produced the same six non-performance artifacts, and had identical artifact hashes. Each invocation also performed its internal repeated-build determinism check. The matching deterministic fingerprint was:

```text
42957fb0df40b6354a7d30385959f05c367485546ce09e3b14ce07ef14841ea1
```

The authoritative database SHA-256 remained `73db5d58f9cc1b2f5723ddbb86678036a6e5c67d322cf492d3b2d0f4d2f23df4` before and after analysis. The existing WAL and SHM sidecar fingerprints also remained unchanged. No ledger, outcome, report, score, provenance, probability field, or schema was modified.

The final scoped regression command was:

```powershell
$env:MARKET_PULSE_DISABLE_BACKGROUND = '1'
python -B -m unittest regression.test_p204_score_bucket_performance regression.test_p2_01_decision_ledger regression.test_p2_02_outcome_evaluation regression.test_p2_03_probability_forecast regression.test_p1d_decision_outcome_ledger regression.test_p1_03_risk_classification
```

Result: **74 tests passed**, including **22 P2-04 tests**. `probabilityLabelAllowed` remains `false`; P2-03 remains `CLOSED` and was not modified.

## Post-closure evidence operations

Future authoritative `EVALUATED` outcomes may be processed by the completed P2-04 analyzer as operational performance evidence accumulation. New data alone does not reopen P2-04 engineering. Any resulting statistics remain descriptive unless a separately authorized frozen protocol establishes stronger evidence criteria.

## Explicit non-claims

This closure makes no claim of realized predictive performance, statistical significance, score monotonicity, probability calibration, profitability, trading edge, or risk-adjusted alpha.

```text
P2-04: CLOSED
RESULT: PASS — ENGINEERING / GOVERNANCE CLOSURE
REALIZED PERFORMANCE EVIDENCE: NOT AVAILABLE — NO ELIGIBLE EVALUATED OUTCOMES
POST-CLOSURE PERFORMANCE EVIDENCE: PENDING FUTURE AUTHORITATIVE OUTCOMES
P2-05: NOT AUTHORIZED / NOT STARTED
P3: NOT AUTHORIZED / NOT STARTED
P4: NOT AUTHORIZED / NOT STARTED
```
