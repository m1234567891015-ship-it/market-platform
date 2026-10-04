# P4-04 Formal Acceptance / Closure

Date: 2026-10-03
Owner authorization: Granted for P4-04 Formal Acceptance / Close only.

## Formal decision

```text
P4-04 — Quant CI / Orphan Regression Cleanup
STATUS: CLOSED
RESULT: PASS — ENGINEERING / GOVERNANCE CLOSURE
QUANT REGRESSION INVENTORY: VERIFIED
QUANT CI COVERAGE: VERIFIED
MANDATORY ORPHAN REGRESSIONS: 0
CI FAILURE PROPAGATION: VERIFIED
KNOWN P4-04 CORRECTNESS / COVERAGE DEFECT: NONE
FORMAL ACCEPTANCE: APPROVED BY PROJECT OWNER
```

## Frozen contract and inventory

- Contract: `docs/P4_04_QUANT_CI_ORPHAN_REGRESSION_CONTRACT.md`
- Contract ID: `P4_04_QUANT_CI_ORPHAN_REGRESSION_V1`
- Contract SHA-256: `1c29612d28801cc3787ebe7794994f6f0f323f1ff13d02fbafc0effe9946df65`
- Inventory: `docs/P4_04_QUANT_REGRESSION_INVENTORY.md`
- Inventory SHA-256: `3ad061c47fe0d96d60e5d29cc52788f07d354a9cf2a2978ebc67cc53045690c4`

Both files were re-hashed during formal acceptance and match the accepted execution evidence byte-for-byte. The machine-readable manifest, inventory rows, runner membership, and coverage regression agree on 37 unique mandatory Quant regressions. All 37 paths exist; no mandatory regression was removed or retired.

## CI coverage and Quant runner

The accepted classification is:

| Classification | Count |
|---|---:|
| `CI_ENFORCED_DIRECT` | 6 |
| `CI_ENFORCED_VIA_QUANT_RUNNER` | 31 |
| Mandatory orphan regressions | 0 |
| Retired regressions | 0 |

The deterministic runner is `regression/run_quant_regressions.py`, driven by the explicit ordered `regression/quant_regression_manifest.json`. The P1 quality-gate workflow invokes the runner and then `regression.test_p404_quant_ci_coverage`. The accepted runner execution passed 37 mandatory regressions: 23 Python unittest suites / 431 unittest cases and 14 Node scripts. This prior execution is accepted by attribution because the contract, inventory, manifest, runner, workflow, coverage regression, and relevant fixtures remain unchanged since that execution; the full gate was not rerun during formal closure.

The P4-04 coverage regression passed 9 tests, including the controlled child-process failure probe: exit code 23 was observed and propagated as a non-zero runner result. The workflow contains no `continue-on-error: true` or `|| true` failure suppression. Mandatory regression failures remain job failures.

## Q2 methodology and test retirement

`regression/test_q2_backtest_methodology.js` retains the `TW_EQUITY` fixture, chronological train/validation/test assertions, `T close` signal timing, `T+1 open` execution timing, untouched-test assertion, and positive round-trip-cost assertion. The accepted focused regression passed. The production cost-model fail-closed behavior was not weakened or redesigned by P4-04.

No regression was retired, deleted, skipped, or converted to warning-only behavior. The two stale UI wording assertions were redirected to the authoritative P4-03 derivatives module while preserving their assertions. The P2-03 replay database guard uses a temporary sentinel under an isolated patched root.

## Workflow and compatibility evidence

- `.github/workflows/p1-quality-gate.yml` YAML parsing: PASS in the prior execution audit; the workflow was unchanged during formal acceptance. The active closure interpreter did not have PyYAML available, so parsing was not repeated.
- Explicit workflow script/module path audit: 36 / 36 paths exist.
- Workflow commands use the repository checkout root by default; all referenced runner and regression paths resolve from that root.
- P4-01 compatibility: `regression.test_p401_builders_fetchers_domain`, 10 tests PASS.
- P4-02 compatibility: `regression/test_p402_shared_calc_hidden_global_state.js`, PASS.
- P4-03 compatibility: `regression/test_p403_giant_page_modules_decomposition.js`, PASS.

These accepted regression results were not rerun during formal closure. Repository workflow wiring was verified; remote GitHub branch-protection settings were not queried or changed.

## Isolation and production boundary

- The Quant runner redirects database and cache environment paths to a temporary isolated directory. The historical replay guard uses an isolated temporary sentinel.
- Authoritative Decision / Outcome database mutation: NONE.
- Mandatory live-provider dependency in the 37-test Quant gate: NONE; provider transports in the audited test set are mocked.
- No production market calculation, signal timing, execution timing, transaction-cost or futures-multiplier semantics, Sharpe / return, VaR / Expected Shortfall, Euler risk contribution, Decision / Outcome, calibration, regime, Walk-Forward, Net Expectancy, Model Drift, or probability semantics were redesigned by P4-04.
- No API baseline, visual baseline, or database schema/data was changed by P4-04.

## Markdown whitespace adjudication

The frozen contract has two trailing spaces on lines 3–4, and the inventory has two trailing spaces on lines 3–6. Each occurrence is intentional Markdown hard-break syntax. No accidental trailing whitespace was found in the P4-04 Markdown artifacts. These are untracked documents, so tracked `git diff --check` does not inspect them; the accepted `git diff --check` result is PASS for tracked changes.

## Explicit non-claims and boundaries

- This closure does not claim remote branch protection was configured or verified.
- This closure does not close Phase 4 as a whole. Phase 4 has 4 / 4 nodes closed and is eligible for a separately authorized Phase 4 Formal Closure, which has not been executed.
- No Git promotion, deployment, or next phase was authorized or performed.

```text
P4-01: CLOSED
P4-02: CLOSED
P4-03: CLOSED
P4-04: CLOSED
PHASE 4 NODE COMPLETION: 4 / 4 CLOSED
PHASE 4 FORMAL CLOSURE: ELIGIBLE / NOT YET EXECUTED
GIT PROMOTION: NOT AUTHORIZED / NOT EXECUTED
DEPLOYMENT: NOT AUTHORIZED / NOT EXECUTED
NEXT PHASE: NOT AUTHORIZED / NOT STARTED
```
