# P2-05 Formal Closure — Engineering / Governance

**Date:** 2026-10-02
**Status:** CLOSED
**Result:** PASS — ENGINEERING / GOVERNANCE CLOSURE
**Owner decision:** Authorized by the Project Owner's `P2-05 — Regime Contract Freeze + Implementation + Engineering / Governance Formal Closure` instruction.

## Frozen contract

- Contract: `P2_05_MARKET_SCORE_REGIME_V1` (V1)
- Contract file: `docs/P2_05_REGIME_PERFORMANCE_CONTRACT.md`
- Contract SHA-256: `e65588e9c771a06b6ee51bccefa0351033420824e77969092a875ac03edd11d2`
- Source: persisted `decision_ledger.decision_output_json.marketScore` only.
- Taxonomy: `LOW` [0,40), `MID` [40,60), `HIGH` [60,100]. Owner-frozen thresholds; no fitting or optimization.
- Decision-time semantics: deterministic analytical classification of the immutable Decision snapshot. No current score, historical score recomputation, future data, Outcome, or ledger backfill is used.
- Invalid/missing scores fail closed as `REGIME_INVALID` for audit and are excluded.

The contract keeps horizons separate and defines eligible observations as unique Decision/horizon joins with matching LONG/SHORT state and direction, explicit boolean `decisionEligible=true`, valid persisted regime score, canonical `EVALUATED` status, compatible `DIRECTIONAL_RETURN` basis, finite `decisionAlignedReturn`, and non-conflicting relationship metadata.

## Implementation

- Analyzer: `scripts/p205_regime_performance.py`
- Regression: `regression/test_p205_regime_performance.py`
- The analyzer uses SQLite `mode=ro&immutable=1`, fingerprints the database and sidecars around reads, writes reports only under `.tmp/p205-regime-performance/`, and never writes to the ledger.
- No production score formula, Decision/Outcome row, probability field, provenance, database schema, P2-03 behavior, or P2-04 behavior was changed.
- `probabilityLabelAllowed` remains explicitly `false` in the persisted Decision.

## Authoritative data and coverage

Database: `data/p203-prospective-ledger.sqlite3`
SHA-256 before and after analysis: `73db5d58f9cc1b2f5723ddbb86678036a6e5c67d322cf492d3b2d0f4d2f23df4`
Decision / Outcome rows: `1 / 0`
Eligible EVALUATED LONG/SHORT observations: `0`
Latest `market_as_of`: `2026-10-01`

The Decision snapshot has `marketScore=50`, `decisionState=NO_TRADE`, `executionDirection=UNAVAILABLE`, `decisionEligible=false`, and `probabilityLabelAllowed=false`. Coverage is `LOW=0`, `MID=1`, `HIGH=0`, `REGIME_INVALID=0` (missing score 0, invalid score 0). This is Decision coverage only.

Point-in-time integrity: **PASS**. Classification reads only the persisted decision-time `marketScore`; it does not recompute or backfill a regime.

Join audit: **PASS**. Joined Outcomes `0`; orphan Outcomes `0`; duplicate Decision/horizon associations `0`; duplicate Decision IDs `0`; Decision/Outcome metadata mismatches `0`; Outcome status conflicts `0`; Outcome basis conflicts `0`; state/direction mismatches `0`.

Realized regime performance:

```text
NOT AVAILABLE — NO ELIGIBLE EVALUATED OUTCOMES
```

No `regime_performance.csv`, synthetic performance rows, zero-return observations, or success-rate claims were generated.

## Regression and deterministic evidence

P2-05 focused regression: **14 tests PASS**. The suite covers all frozen boundaries, invalid scores, persisted Decision-time-only classification, LONG/SHORT positive and negative directional returns, exact metrics in all three regimes, horizon separation, all specified ineligible states/statuses, invalid returns/bases, orphan and duplicate joins, metadata conflicts, zero-evidence output behavior, read-only SQLite inventory, deterministic artifacts, and the false probability-label gate. A threshold fault-injection check was detected by the boundary assertion.

Required scoped command, with `MARKET_PULSE_DISABLE_BACKGROUND=1`:

```powershell
python -B -m unittest regression.test_p205_regime_performance regression.test_p204_score_bucket_performance regression.test_p2_01_decision_ledger regression.test_p2_02_outcome_evaluation regression.test_p2_03_probability_forecast regression.test_p1d_decision_outcome_ledger regression.test_p1_03_risk_classification
```

Result: **88 tests PASS**. Python AST syntax check for the analyzer and new regression: **PASS**.

The authoritative analyzer ran twice against the same immutable input. All four analysis artifact hashes matched between runs. Deterministic fingerprint: `6320c04f87d3e15898d9181c17206fcaa59c8ef166c4f9c79e724e92c17b3bbb`. The report omitted `regime_performance.csv` because the eligible denominator is zero. Database and WAL/SHM sidecar fingerprints matched before and after each read.

## Engineering readiness and evidence maturity

P2-05 engineering readiness: **PASS**. All contract, taxonomy, PIT, eligibility, integrity, coverage, zero-evidence, synthetic metric, read-only, database-immutability, determinism, probability-gate, and regression criteria passed.

Realized regime performance evidence maturity: **NOT AVAILABLE — NO ELIGIBLE EVALUATED OUTCOMES**. Future authoritative Outcomes may be processed as `POST-P2-05 OPERATIONAL REGIME PERFORMANCE EVIDENCE`; their arrival alone does not reopen P2-05 engineering.

## Explicit non-claims

This closure establishes no regime predictive validity, statistical significance, regime monotonicity, profitability, trading edge, alpha, or probability-label promotion. All future regime metrics remain descriptive unless a separately authorized statistical protocol establishes otherwise.

```text
P2-05: CLOSED
RESULT: PASS — ENGINEERING / GOVERNANCE CLOSURE
REGIME CONTRACT: P2_05_MARKET_SCORE_REGIME_V1
REALIZED REGIME PERFORMANCE EVIDENCE: NOT AVAILABLE — NO ELIGIBLE EVALUATED OUTCOMES
POST-CLOSURE REGIME PERFORMANCE EVIDENCE: PENDING FUTURE AUTHORITATIVE OUTCOMES
P2-03: CLOSED
P2-04: CLOSED
P3: NOT AUTHORIZED / NOT STARTED
P4: NOT AUTHORIZED / NOT STARTED
```
