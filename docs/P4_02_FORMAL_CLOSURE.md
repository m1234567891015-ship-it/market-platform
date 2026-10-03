# P4-02 Formal Closure

**Date:** 2026-10-03

**Owner authorization:** `P4-02 — FORMAL ACCEPTANCE / CLOSE`

**Node:** P4-02 — Shared-calc Remove Hidden Global State

## Formal decision

```text
P4-02: CLOSED
RESULT: PASS — ENGINEERING / GOVERNANCE CLOSURE
HIDDEN GLOBAL SEMANTIC STATE: REMOVED / VERIFIED
EXPLICIT INPUT CONTRACT: VERIFIED
REPLAY / DETERMINISM: PASS
KNOWN P4-02 CORRECTNESS DEFECT: NONE
FORMAL ACCEPTANCE: APPROVED BY PROJECT OWNER
```

## Frozen contract

Contract ID: `P4_02_SHARED_CALC_EXPLICIT_INPUT_V1`

File: `docs/P4_02_SHARED_CALC_HIDDEN_GLOBAL_STATE_CONTRACT.md`

SHA-256: `f00339c4020ee4c1be6e73811d55d23464f6a18d5af4074447928b47348c90e0`

The contract was re-hashed during formal acceptance and remains byte-identical to the authorized frozen contract.

## Accepted defect and remediation

The `js/shared-calc.js` audit covered 466 function-like nodes. It identified six hidden semantic reads in `buildInstitutionalBacktestFramework`, sourced from ambient `data` fields for international indexes, macro factors, volatility, and market overview. The accepted P4-02 regression now reports zero hidden semantic reads, zero semantic global writes, and zero justified ambient semantic reads inside calculation logic.

`buildInstitutionalBacktestFramework` takes an explicit `marketContext`; `analyzeTechnicalTheories` accepts and forwards it. All six sanctioned page callers obtain it through the existing `twEtfState.getMarketBreadthContext` adapter. The page/state adapter remains the permitted place to collect current application state. No module decomposition or unrelated global-state migration was performed.

## Input, replay, and formula semantics

The accepted regression proves that identical explicit inputs produce identical results after unrelated ambient state changes, while changing explicit market context changes the relevant market calculation. Historical fixtures supply their own context; the calculation does not look up current page data, latest global state, or future context during replay.

With the known explicit regression fixture, framework total score is `59`, market layer score is `56.607142857142854`, market state is `Neutral`, and market-layer coverage is 100%. Without context, the existing missing-data behavior remains score `50` and coverage `0%`; no ambient fallback is used. These values are regression evidence, not production constants.

No trend, risk, market score, evidence score, data-quality score, regime, Decision, Outcome, probability-model, transaction-cost, or P3 validation formula was changed. The affected calculation uses no cache. The Q2 fixture explicitly declares `assetClass: "TW_EQUITY"`; the existing unsupported/unknown-class fail-closed cost rule remains intact.

## Determinism and regression evidence

Accepted P4-02 audit evidence:

```text
Source SHA-256: ac3cf6fe2d77dd7dc6d6bff75c89a9e28a12010d66c6800bb5c0edfc73a4628f
Fingerprint:    e2f2c07c5b7fdae21476a03f88c672aecf18b819298821f1cda363cbba57fec8
Result:         two runs matched
```

During formal acceptance, the contract hash and source SHA/fingerprint were rechecked by running `node regression/test_p402_shared_calc_hidden_global_state.js`; all values still match the accepted evidence. The Q2 fixture classification was checked in the current test file.

The prior execution report recorded passing results for:

- `node regression/test_p2_frontend_contract.js`
- `node regression/test_q5_quant_math.js`
- `node regression/test_p1c_sharpe_return_semantics.js`
- `node regression/test_p0b1_futures_backtest_cost_wiring.js`
- `node regression/test_q2_backtest_methodology.js`
- JavaScript / ESM syntax checks and `git diff --check`
- `python -B regression/td18_minify_verify.py`
- `python -B regression/td18_shadow_verify.py`
- `python -B regression/td02_full_esm_canary.py`: 42/42 runs across 21 pages, ESM and Classic fallback

Those full execution-cycle checks were not rerun solely for closure. Their source and runtime evidence remains attributable: the accepted focused regression emits the same source SHA/fingerprint, and the current ESM and Classic artifact hashes match their build manifests. The ESM build version recalculates to the recorded version.

P4-01 compatibility was freshly rechecked during closure with `python -B -m unittest regression.test_p401_builders_fetchers_domain`: 10 tests passed. P4-01 remains CLOSED.

Runtime identities remain:

```text
Classic: td18-minify-65361d88eb8686ae
ESM:     td02-full-esm-0f47d0e4d4e6b961
```

The Classic and ESM rebuilds are local compatibility artifacts, not P4-03 decomposition. No runtime deployment occurred.

## Data and scope boundaries

```text
AUTHORITATIVE DB MUTATION: NONE
LIVE PROVIDER REQUEST: NONE
P4-01: CLOSED
P4-03: NOT AUTHORIZED / NOT STARTED
P4-04: NOT AUTHORIZED / NOT STARTED
PHASE 4 FORMAL CLOSURE: NOT ELIGIBLE YET
GIT PROMOTION: NOT AUTHORIZED
DEPLOYMENT: NOT AUTHORIZED
```

No Decision/Outcome database was opened or modified. This closure makes no claim about profitability, predictive validity, statistical significance, or production deployment. `shared-calc.js` decomposition remains a P4-03 concern; Quant CI and orphan cleanup remain P4-04 concerns.
