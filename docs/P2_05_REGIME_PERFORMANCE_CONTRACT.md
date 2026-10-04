# P2-05 Regime Performance Contract

## Identity and scope

- Contract: `P2_05_MARKET_SCORE_REGIME_V1`
- Version: V1
- Purpose: descriptive performance of eligible P2-01 Decisions grouped by a deterministic regime derived from their persisted decision-time `marketScore`.
- Thresholds are Project Owner-frozen governance thresholds. They are predefined, not learned, optimized, or selected from realized performance.
- This contract does not alter Decision Ledger, Outcome, score generation, probability display, schema, or P2-04 score-bucket behavior.

## Regime source and taxonomy

Read only `decision_ledger.decision_output_json.marketScore`, the value captured in the persisted Decision snapshot. Do not use current/runtime scores, recompute historical scores, use future prices or Outcomes, or write a derived label back to the ledger.

| Label | Inclusive lower bound | Upper bound | Upper-bound rule |
|---|---:|---:|---|
| `LOW` | 0 | 40 | exclusive |
| `MID` | 40 | 60 | exclusive |
| `HIGH` | 60 | 100 | inclusive |

Thus 0 and 39.999 map to `LOW`; 40 and 59.999 map to `MID`; 60 and 100 map to `HIGH`. There are no gaps or overlaps. These labels describe score ranges only; they do not mean bearish, neutral, bullish, favorable, or unfavorable.

## Score validity and coverage

The persisted score must be a finite JSON numeric value (booleans are not numeric for this contract) in the closed interval [0, 100]. Missing/null, nonnumeric, nonfinite, or out-of-range values are `REGIME_INVALID` for audit and are excluded from performance. Coverage reports `LOW`, `MID`, `HIGH`, and invalid/missing scores separately; it is Decision coverage, not realized-performance coverage.

## Decision-time and Outcome eligibility

One eligible performance observation is a unique `(Decision ID, evaluation_horizon)` association satisfying all of the following:

- Decision state and execution direction are both `LONG` or both `SHORT`.
- Persisted `decisionEligible` is exactly boolean `true`.
- Persisted decision-time `marketScore` is valid and maps to one of the three labels.
- Outcome status is canonical `EVALUATED`; any stored `outcomeStatus` metadata agrees.
- Outcome metadata `evaluationBasis` is `DIRECTIONAL_RETURN` and `decisionAlignedReturn` is a finite numeric value.
- Decision/Outcome IDs and horizon metadata agree; the association is unique and not orphaned or ambiguous.

Exclude `NO_TRADE`, `HOLD_EXISTING`, `UNKNOWN`, other non-directional or state/direction-mismatched Decisions, false/missing/unknown/nonboolean eligibility, every non-`EVALUATED` status, invalid scores, incompatible Outcome bases, invalid returns, orphan/duplicate associations, and conflicting metadata. They are audit exclusions, never zero-return observations.

Outcome horizons remain separate. Results are grouped by `(regime, evaluation_horizon)`; horizons are not pooled. Use the P2-02 `decisionAlignedReturn` semantics already consumed by P2-04.

## Metrics and evidence qualification

For each regime/horizon with eligible observations, report `n` (also the `EVALUATED` count), positive, negative, and flat directional outcomes, success rate, mean return, and median return. Success rate is `positive / (positive + negative)`; it is null when there are no non-flat outcomes. Mean and median use all eligible finite decision-aligned returns, including flat returns.

Every result is labeled `DESCRIPTIVE REGIME PERFORMANCE` and exposes `n`. No minimum sample threshold or significance test is defined. Do not claim statistical validity, predictive validity, monotonicity, profitability, trading edge, or alpha.

## Zero-evidence behavior

When eligible `EVALUATED` LONG/SHORT observations equal zero, report:

```text
REALIZED REGIME PERFORMANCE:
NOT AVAILABLE — NO ELIGIBLE EVALUATED OUTCOMES
```

Emit diagnostic coverage, join, eligibility, and summary artifacts only. Do not write `regime_performance.csv`, zero-valued performance rows, or synthetic performance conclusions.

## Read-only and future evidence semantics

The analyzer opens the authoritative SQLite database read-only/immutable where supported, records database and sidecar fingerprints, and does not mutate Decisions, Outcomes, reports, scores, probabilities, provenance, or schema. Synthetic fixtures are test evidence only.

After engineering closure, new authoritative Outcomes may be analyzed as `POST-P2-05 OPERATIONAL REGIME PERFORMANCE EVIDENCE`; their arrival alone does not reopen the engineering node. Evidence maturity remains separate from engineering readiness.

`probabilityLabelAllowed` remains false. Any taxonomy, threshold, source, or timestamp-semantic change requires a new contract version and Project Owner authorization.
