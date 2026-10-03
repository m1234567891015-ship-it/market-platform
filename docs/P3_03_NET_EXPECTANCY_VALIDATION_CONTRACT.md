# P3-03 Net Expectancy Validation Contract

- **Contract ID:** `P3_03_NET_EXPECTANCY_VALIDATION_V1`
- **Status:** `FROZEN`
- **Authority:** Project Owner P3-03 authorization
- **Scope:** Read-only engineering and descriptive validation of realized, cost-adjusted directional Outcomes. This contract does not close P3-03.

## 1. Frozen dependencies

- Phase baseline: `PHASE3_MODEL_VALIDATION_V1`, SHA-256 `43ebcad66cd8267c07bca2419fbbcdeca066e6195eecf1e4ac782fd5954bbc57`.
- P3-01 and P3-02 are formally closed. Their contracts and implementations are dependencies and remain unchanged.
- Eligibility semantics: P2-04's canonical evaluated directional Decision/Outcome semantics, including strict boolean eligibility, matched LONG/SHORT state and direction, `DIRECTIONAL_RETURN`, immutable decision values, unique association, and fail-closed exclusions.
- Outcome contract: P2-02 `P2_02_OUTCOME_V1` / `P2_02_DIRECTIONAL_OUTCOME_V1`.
- Cost contract: decision-time `P0B_FUTURES_COST_V1`; no cost recalculation or substitution is performed by P3-03.
- Authoritative input: the existing P2-01 Decision Ledger and P2-02 Outcome table in `data/p203-prospective-ledger.sqlite3`, opened read-only.

## 2. Population and eligibility

The analysis considers only the unique `(decision_id, T+1)` association. `T+1` retains P2-02's next observed market-session meaning. Each Decision and Outcome remains immutable and separate. Decisions and Outcomes are never backfilled, reconstructed, or joined by inferred identity.

An Outcome enters the P2-04 eligible directional denominator only when all conditions hold:

1. A unique persisted Decision exists and the Outcome association is not orphaned, duplicated, or contradicted by stored Decision ID / horizon metadata.
2. Persisted Outcome status is canonical `EVALUATED`, agrees with any `outcomeStatus` metadata, its basis is `DIRECTIONAL_RETURN`, and its `outcomeSchemaVersion` / `evaluationContractVersion` exactly identify `P2_02_OUTCOME_V1` / `P2_02_DIRECTIONAL_OUTCOME_V1`.
3. Persisted `decisionEligible` is exactly boolean `true`; `decisionState` and `executionDirection` are the same value, `LONG` or `SHORT`.
4. `decisionAlignedReturn` is finite numeric evidence, as required by the P2-04 eligibility semantics.
5. Decision and evaluation timestamps parse as timezone-aware timestamps and evaluation time is strictly later than decision time.

`NO_TRADE`, `HOLD_EXISTING`, missing / malformed eligibility, invalid direction, invalid status or basis, malformed timestamps, orphan / duplicate / conflicting associations, and non-T+1 horizons are excluded and counted by reason. Gross directional return is an eligibility consistency input only; it is never the P3-03 expectancy value.

## 3. Canonical realized return and cost treatment

The canonical expectancy observation is the persisted `decision_outcome.net_return`, a fractional cost-adjusted return (`costAdjustedReturnPct / 100`) produced by P2-02. It is usable only when the same persisted row also proves a supported decision-time cost result:

- `cost_adjusted_result_json.status == "AVAILABLE"`;
- `contractVersion == "P0B_FUTURES_COST_V1"` in both the Decision's frozen `execution_cost_assumptions_json` and the Outcome cost result;
- Outcome metadata declares `strategyEvaluationBasis == "STRATEGY_RETURN"` and its `strategyReturn` matches the dedicated persisted cost-adjusted result;
- instrument identity and currency agree with the supported P0B contract;
- `net_return` is finite and agrees with `costAdjustedReturnPct / 100`;
- `execution_cost` is finite, nonnegative, and agrees with the persisted cost result's `totalCost`;
- cost components reconcile to `totalCost`, `netPnl` reconciles to `grossPnl - totalCost`, and `costAdjustedReturnPct` reconciles to `grossDirectionalReturnPct - normalizedCostPct`;
- the gross values in P2-02 (`gross_return`, `decisionAlignedReturn`, `grossDirectionalReturnPct`) are finite and mutually consistent.

Numeric reconciliation uses only floating-point representation tolerance: relative tolerance `1e-12`, absolute tolerance `1e-12` for return fractions / percentage points and `1e-9` for currency amounts. This tolerance does not alter P2-02 values or define an economic threshold. Missing, unsupported, nonfinite, negative-cost, version-mismatched, or unreconciled evidence is excluded with an explicit reason; it is never imputed or recomputed using a new cost formula.

## 4. Aggregation and metrics

- Aggregate separately by the frozen P0B instrument (`TX`, `MTX`, `TMF`, `TE`, or `TF`), cost contract version, and currency. Do not pool instruments or currencies.
- No regime-conditioned P3-03 metric is defined. P2-05 / P3-02 regime labels and boundaries remain unchanged and are not used to partition P3-03 expectancy.
- Included sample `N` counts only cost-qualified observations. Positive, negative, and zero / flat counts use the sign of canonical `net_return`; zero remains in the arithmetic mean and denominator.
- Canonical net expectancy is the arithmetic mean of all included fractional `net_return` values. Win Rate is `positive / (positive + negative)` and is null when there are no non-flat returns. Average Win and Average Loss are conditional arithmetic means of positive and negative net returns respectively, null when their side has no observations.
- The decomposition is `positiveCount/N * averageWin + negativeCount/N * averageLoss + zeroCount/N * 0`, and must reconcile to canonical net expectancy within the return tolerance. No alternative expectancy formula is permitted.
- Report minimum / maximum net return and total / average execution cost only when included observations exist.
- Do not report cumulative return: no frozen capital allocation, overlapping-position, reinvestment, or portfolio aggregation semantics establish that such a cumulative figure would represent the realized strategy.
- No frozen P3-03 statistical sufficiency threshold exists. Report sample counts, return-side coverage, and `SAMPLE SUFFICIENCY: NOT DEFINED — DESCRIPTIVE ONLY`; do not infer statistical maturity or PASS from engineering readiness.
- With no included observations, expectancy and all sample metrics are `null` / `NOT AVAILABLE`, never zero.

## 5. Chronology, determinism, and evidence class

- Only immutable decision-time ledger snapshots and their separately persisted T+1 Outcomes are read. No Outcome may contribute unless its timezone-aware evaluation time is strictly after its Decision time.
- No score, forecast, future value, later cost assumption, or outcome label may change Decision-time eligibility or cost assumptions.
- Pure fixture analysis defaults to `SYNTHETIC_TEST_ONLY`; synthetic values must never be reported as authoritative evidence.
- Authoritative CLI analysis is pinned to the canonical prospective DB. It records main DB, WAL, and SHM SHA-256 fingerprints, SQLite application ID, integrity check, schema fingerprint, row counts, and the eligible evaluated directional count before and after. Any database change, failed integrity check, wrong DB identity, malformed ledger payload, or before/after difference blocks the authoritative report.
- Canonical JSON uses sorted keys, compact separators, UTF-8, and rejects NaN / Infinity. Identical inputs and contract must produce identical report fingerprints in independent processes.
- Deterministic ordering is by decision time, decision ID, horizon, then instrument / scope and stable exclusion reason.

## 6. Sample sufficiency and claims

Engineering status and validation-pipeline readiness are reported separately from evidence availability. A correctly functioning empty-sample pipeline may be READY while realized expectancy remains NOT AVAILABLE and evidence remains NOT YET MATURE. P2-03's 30-label / both-class gate applies to its frozen probability-model training and P3-01 OOS maturity; it is not imported as a P3-03 expectancy threshold.

P3-03 does not claim profitability, positive expectancy, alpha, trading edge, future performance, statistical significance, model superiority, regime superiority, probability calibration, or probability-label approval. `probabilityLabelAllowed` remains false. No target, horizon, feature, threshold, regime boundary, production decision, cost model, or upstream contract is modified.

## 7. Frozen implementation identity

Before P3-03 implementation begins, this document's SHA-256 is recorded in the implementation and regression. Any later semantic change requires a new contract version and Project Owner authorization. This contract and its execution do not authorize P3-04, Phase 4, formal P3-03 closure, Git promotion, deployment, or authoritative DB mutation.
