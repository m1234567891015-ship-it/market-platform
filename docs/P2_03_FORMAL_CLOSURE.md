# P2-03 Final Simplification / Amendment 002 / Formal Closure

**Closure date:** 2026-10-02
**Authority:** Project Owner, authorization `P2-03 — FINAL SIMPLIFICATION + AMENDMENT 002 + FORMAL CLOSURE`
**Scope:** P2-03 engineering and governance closure only

## Final status

```text
P2-03:
CLOSED

RESULT:
PASS — ENGINEERING / GOVERNANCE CLOSURE

Historical V2:
RESEARCH_ONLY / COMPLETE AS RESEARCH DIAGNOSTIC

Prospective Pipeline:
ENGINEERING READY

Prospective Statistical Maturity:
PENDING FUTURE REAL OBSERVATIONS

probabilityLabelAllowed:
false
```

P2-03 is closed because the production prospective probability pipeline, its chronology controls, provenance controls, outcome contract, cold-start behavior, model execution gate, and fail-closed behavior have been implemented and deterministically verified. Historical V2 has been formally reclassified as research-only after deterministic evidence showed the frozen historical window cannot satisfy the frozen minimum training requirement. Future prospective observations continue to accumulate operational evidence but do not keep the engineering node open.

## Historical finding and adjudication

The immutable historical evidence consists of 441 selected sessions, 23 contract runs, 22 transitions, 19 matured eligible labels, zero forecasts, and zero OOS pairs. The 30-label minimum cannot be reached in this fixed window under the frozen same-contract D−20 through D+1 continuity contract. The classification is `HISTORICALLY INFEASIBLE UNDER CURRENT CONTRACT`, limited to this contract and dataset. Source publication timing, historical vintage, and revision history remain `NOT PROVEN`.

The Project Owner adjudicated daily highest-volume selected-contract data combined with 20-session same-contract feature continuity and same-contract T+1 target continuity as over-constrained for this available historical series. Historical V2 is complete as a diagnostic method record, not as forecast or production validation. Its 19/0/0 results and all inputs, traces, manifests, audit outputs, and counterfactuals remain preserved. Counterfactual lookbacks remain non-authoritative and none is adopted.

Amendment 002: `docs/P2_03_PROTOCOL_AMENDMENT_002.md`
Amendment 002 SHA-256: `3b3d2b37aef0a0480ec6c0ac6aab8387c0b4ed4c53b8f9f8801025c41002f376`
Previous effective identity (Original + Amendment 001): `f229f03eb3d931aae96d1e994cb8725f8a73676132632da28c94cc9e4d8fcafc`
New effective identity (Original + Amendment 001 + Amendment 002): `8783fb841427ee1fba44ac93d3f2e1186850b179fd4042777664f0c211e174f3`

## Production contract retained

- Features remain exactly `marketScore`, `riskScore`, `evidenceScore`, and `dataQualityScore` under `P2_03_DERIVATIVES_SCORE_FEATURES_V1`.
- Target remains `DIRECTIONAL_SUCCESS` over the T+1 observed market session; only eligible LONG/SHORT decisions qualify. Positive aligned return maps to 1, negative to 0, and exact zero is excluded.
- The existing deterministic logistic model is unchanged.
- At least 30 eligible matured prior labels and both classes are required. Zero to 29 labels fail closed; single-class training fails closed.
- Decision rows remain immutable and append-only; Outcome data remains separate. No historical provenance or outcome backfill occurred.
- Source roles remain differentiated, including Primary, Supplement, Explicit Yahoo, Automatic Fallback, and UNKNOWN.
- `probabilityLabelAllowed` remains false. P2-03 closure does not authorize end-user probability labels.

## Prospective readiness acceptance matrix

| Check | Result | Evidence |
|---|---|---|
| Duplicate market session does not add a Decision | PASS | Isolated runner and closure regression |
| New NO_TRADE Decision persists ineligible with null forecast | PASS | Isolated ledger closure regression |
| Eligible LONG / SHORT with fewer than 30 labels fail closed | PASS | Isolated ledger plus probability contract tests |
| NO_TRADE / HOLD_EXISTING are not training labels | PASS | P2-02 and P2-03 regression tests |
| Eligible LONG / SHORT T+1 labels follow aligned-return sign | PASS | Probability target and Outcome tests |
| 30 balanced labels execute the synthetic model path | PASS | Amendment 002 closure regression |
| 30 single-class labels fail closed | PASS | Amendment 002 closure regression |
| Future/unmatured training rows do not enter earlier fits | PASS | Probability chronology/future-row tests |
| Historical null provenance is not backfilled | PASS | Source provenance Ledger round-trip test |
| API/Ledger prospective forecast round trip preserves fail-closed label policy | PASS | Probability forecast API/Ledger tests |
| Score values are inputs, not copied as probability | PASS | Synthetic fixture: marketScore 68 produced 0.746169790163 |
| `probabilityLabelAllowed` remains false | PASS | API and Ledger assertions |

All synthetic examples are `TEST EVIDENCE ONLY`, not real prospective observations.

## Regression and data integrity

Final scoped regression command:

```powershell
$env:MARKET_PULSE_DISABLE_BACKGROUND = '1'
python -B -m unittest regression.test_fetch_registry_bom regression.test_p0a_market_time_integrity regression.test_p203_source_provenance regression.test_p203_prospective_evidence_runner regression.test_p2_02_outcome_evaluation regression.test_p2_03_probability_forecast regression.test_p203_v2_historical_development regression.test_p203_amendment_002_closure
```

Result: `67 tests PASS` (after final deterministic rerun). This includes parser/time-integrity checks, isolated API/Ledger and prospective tests, frozen V2 deterministic checks, roll-continuity feasibility assertions, and Amendment 002 contract assertions.

Authoritative database `data/p203-prospective-ledger.sqlite3`, inspected only through immutable read-only connections:

```text
Before SHA-256: 73db5d58f9cc1b2f5723ddbb86678036a6e5c67d322cf492d3b2d0f4d2f23df4
After SHA-256:  73db5d58f9cc1b2f5723ddbb86678036a6e5c67d322cf492d3b2d0f4d2f23df4
decision_ledger: 1
decision_outcome: 0
```

No live capture ran. The existing Decision's null provenance was not changed. No production algorithm, feature, target, model, schema, or score was changed.

## Prospective operation and non-claims

Prospective Evidence Accumulation is an `ACTIVE OPERATIONAL PROCESS` after closure. Current eligible matured labels are 0. Forecast production still requires at least 30 eligible matured labels and both classes. Probability-label promotion requires a separate future evidence and owner adjudication gate.

This closure does not establish historical predictive validity, prospective predictive validity, positive Brier Skill Score, AUC above 0.5, calibration quality, profitability, probability-label approval, or a production trading edge. No such statistical evidence exists in this closure record.

## Downstream state and authorization boundary

```text
P2-04: BLOCKED — NO ELIGIBLE EVALUATED OUTCOMES
P2-05: NOT AUTHORIZED / NOT STARTED
P3: NOT AUTHORIZED / NOT STARTED
P4: NOT AUTHORIZED / NOT STARTED
```

P2-04 was not run. No downstream node was created or started. This closure authorizes no Git promotion, live capture, deployment, or other node.

## Deterministic closure manifest

Manifest and new effective identity are retained under `.tmp/p203-formal-closure-final/`. The manifest covers the original protocol, Amendments 001 and 002, effective identity, frozen historical inputs, feasibility audit, closure document, canonical status, prospective implementation, and scoped regressions. A second generation in `.tmp/p203-formal-closure-final-repeat/` produced identical hashes. The manifest is local integrity evidence and is not a Git commit or statistical validation.
