# P2-03 Protocol Amendment 002 — Historical Gate Simplification

- **Amendment ID:** `P2_03_PROTOCOL_AMENDMENT_002`
- **Status:** `FORMALLY APPROVED BY PROJECT OWNER`
- **Approval date:** `2026-10-02`
- **Scope:** P2-03 closure criteria and evidence classification only
- **Effective protocol composition:** Original V2 pre-registration + Amendment 001 + this Amendment 002

## Purpose

This amendment removes historical V2 forecast generation and historical V2 OOS generation from the P2-03 engineering closure gate. The Project Owner has adjudicated that the fixed historical series selection and frozen same-contract continuity window over-constrain this particular historical dataset. Production safety requirements and the prospective evidence contract remain in force.

This amendment does not change the original V2 pre-registration, Amendment 001, historical inputs, historical outputs, production forecast algorithm, or probability-label policy. It does not authorize another historical model or select a replacement roll lookback.

## Evidence basis and adjudication

The deterministic read-only feasibility audit reloaded 24 saved TAIFEX response windows and reproduced the frozen 441-session daily highest-volume selected-contract series and trace. Verified selected-series SHA-256: `90ca05e0472b09ba3f67e641dae16f8ed9ad310fc87d056e7fd2c3e0baa1c48f`; selection-trace SHA-256: `a1f5bfd250f1cb94f09a7324f5314686fc29e298cde649a26dd4f817e11e251a`.

The fixed series contains 23 contract runs and 22 transitions; median run length is 19 sessions. Under the frozen rule requiring the selected contract to remain the same from D−20 through D+1, the exact funnel is 441 sessions, 401 roll-ineligible rows, 19 matured eligible labels, 0 forecasts, and 0 OOS pairs. The frozen minimum requires at least 30 prior matured labels and both classes. The counterfactual diagnostics yielded 86 labels at 15 sessions, 190 at 10, 294 at 5, and 399 with target-only continuity; these remain non-authoritative diagnostics and do not select a replacement setting.

The Owner adjudicates the combination of daily highest-volume contract selection, 20-session same-contract feature continuity, and same-contract T+1 target continuity as an over-constrained historical research design for this available selected-series structure. The resulting formal historical classification is:

```text
HISTORICALLY INFEASIBLE UNDER CURRENT CONTRACT
```

This finding applies only to the current frozen V2 contract and the current frozen historical development dataset. It does not establish that prospective probability forecasting is impossible.

## Historical V2 status and role

```text
Historical V2:
RESEARCH_ONLY / COMPLETE AS RESEARCH DIAGNOSTIC

Historical Forecast Validation:
NOT AVAILABLE

Historical Production Validation:
NOT ESTABLISHED

Reason:
FROZEN HISTORICAL CONTRACT INSUFFICIENT SAMPLE CAPACITY
```

Historical V2 may support diagnostic development, methodology research, roll-continuity research, and feature research. It is not production probability validation, independent final validation, or a P2-03 closure prerequisite. Preserve the pre-registration, Amendment 001, all 441-session inputs and selection trace, the historical audit, and counterfactual diagnostics unchanged. Preserve the historical result of 19 labels, 0 forecasts, and 0 OOS pairs.

Historical publication timing, vintage, and revision history remain `NOT PROVEN`. No counterfactual is approved as a replacement model, contract, or lookback.

## Prospective production evidence authority

Production probability evidence shall be prospective. Newly generated production probability evidence must use provenance `PROSPECTIVE_DECISION_TIME_MODEL_OUTPUT` and the existing prospective Decision → matured Outcome → OOS-pair path. Future evidence accumulation occurs operationally after P2-03 closure and does not keep the engineering node open solely because calendar time is needed to accumulate observations.

The existing prospective contract remains unchanged:

- Feature contract: `P2_03_DERIVATIVES_SCORE_FEATURES_V1`; exactly `marketScore`, `riskScore`, `evidenceScore`, and `dataQualityScore`.
- Target: `DIRECTIONAL_SUCCESS`, defined for eligible LONG/SHORT decisions at T+1 observed market session.
- Label: positive decision-aligned return is 1; negative is 0; exact zero is `EXCLUDED_FLAT`.
- Model: existing deterministic logistic regression contract; no algorithm, coefficient, or feature changes in this amendment.
- Training gate: at least 30 eligible, matured prior labels and both target classes.
- Decision Ledger remains append-only. Outcomes remain separate from Decision rows. No historical Decision rewrite or backfill is permitted.

## Engineering completion and statistical maturity

P2-03 engineering completion means the prospective probability pipeline is implemented, deterministic, fail-closed, chronology-safe, provenance-safe, and ready to accumulate real prospective evidence. Engineering closure does not mean that the probability model has demonstrated predictive value.

Prospective statistical maturity remains pending future real observations and a separate evidence/promotion adjudication. Current eligible matured labels: `0`. Forecast generation requires at least 30 eligible matured labels and both classes. Probability labels remain unavailable until a separate future approval gate passes.

## Unchanged safeguards and contracts

The following requirements remain mandatory and are not relaxed by this amendment:

- Strictly-prior training chronology; a matured outcome must precede the forecast decision time.
- Feature timestamps must be no later than the decision timestamp; fit cutoff must be earlier than forecast decision time.
- Decision immutability, separate Outcome storage, duplicate-session protection, and source provenance.
- T+1 means the next observed market session, not the next calendar day.
- Only eligible LONG/SHORT decisions train the directional target.
- `NO_TRADE` is `NOT_APPLICABLE`; `HOLD_EXISTING` is `NOT_APPLICABLE` without valid position-entry context.
- Zero-return labels are excluded; invalid or incomplete evidence fails closed.
- Zero to 29 eligible matured labels produce `probabilityForecast=null` and `INSUFFICIENT_TRAINING_HISTORY`; there is no fallback probability.
- At least 30 labels with both classes are required; single-class training fails closed.
- `Score != Probability`; `Scenario Weight != Probability`; `Win Rate != Probability Forecast`.
- `probabilityLabelAllowed=false` at P2-03 closure. Closing P2-03 cannot enable user-facing probability claims.
- Preserve source-role distinctions `TAIFEX_PRIMARY`, `YAHOO_SUPPLEMENT`, `YAHOO_EXPLICIT`, `YAHOO_AUTO_FALLBACK`, and `UNKNOWN`; `YAHOO_SUPPLEMENT` is not `YAHOO_AUTO_FALLBACK`.

The existing historical Decision `cd5434d8bf864e83a9eaf22382b859ee0d89a6da247d837ef968825935ff7267` remains immutable; its null `source_provenance` is not backfilled. No realized result is added to a Decision row.

## Explicit non-claims

Neither this amendment nor P2-03 engineering closure establishes historical or prospective predictive validity, positive Brier Skill Score, AUC above 0.5, calibration quality, profitability, probability-label approval, or a production trading edge. Those claims require future evidence and separate adjudication. Synthetic tests are test evidence only and are not prospective observations.

## Authorization and boundary

The Project Owner's authorization titled `P2-03 — FINAL SIMPLIFICATION + AMENDMENT 002 + FORMAL CLOSURE` formally approves this amendment and permits P2-03 closure only after all acceptance criteria in that authorization pass. P2-04 remains blocked for lack of eligible evaluated outcomes. P2-05, P3, and P4 remain unauthorized and not started. This amendment grants no Git promotion, deployment, live capture, or downstream-node authorization.
