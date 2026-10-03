# P4-04 Quant Regression Inventory / CI Coverage Audit

Date: 2026-10-03  
Contract: `P4_04_QUANT_CI_ORPHAN_REGRESSION_V1`  
Contract file: `docs/P4_04_QUANT_CI_ORPHAN_REGRESSION_CONTRACT.md`  
Contract SHA-256: `1c29612d28801cc3787ebe7794994f6f0f323f1ff13d02fbafc0effe9946df65`  
Machine-readable membership: `regression/quant_regression_manifest.json`

## Quant gate architecture

```text
.github/workflows/p1-quality-gate.yml
  → quality-gate job (pull_request; push to main)
    → python -B regression/run_quant_regressions.py
      → regression/quant_regression_manifest.json (fixed ordered membership)
        → 37 quantitative regression files
```

The coverage regression runs in the same job after the gate. The runner fails fast and returns the failing child's non-zero exit code. Its Python DB/cache environment points to a newly created system temporary directory; the in-scope tests use deterministic fixtures and no live provider. The remote branch-protection required-check list was not available from repository files and was not queried or changed.

The complete local command `python -B regression/run_quant_regressions.py` passed all 37 manifest entries: 23 Python unittest suites / 431 unittest cases and 14 Node scripts, in 196.70 seconds. The suite count is not an assertion count.

At audit start, seven tests had direct workflow invocations and 30 had no actual CI execution path. The P1 workflow's direct `test_q5_quant_math.js` command was consolidated into the Quant runner; six direct invocations remain in the independent P2 release workflow. The 30 prior orphans now have deterministic suite paths, all 37 tests are CI-reached, and the final mandatory orphan count is zero. A test mentioned only in P2 provenance metadata was not treated as executed; its workflow does not run that test matrix.

| Final classification | Count |
|---|---:|
| CI_ENFORCED_DIRECT | 6 |
| CI_ENFORCED_VIA_SUITE | 31 |
| LOCAL_ONLY_VALID | 0 |
| ORPHAN | 0 |
| SUPERSEDED_CANDIDATE | 0 |
| INVALID / BROKEN | 0 |
| OUT_OF_SCOPE adjacent candidates | 9 |

No regression was retired.

## In-scope quantitative regressions

`Local status` records the final local gate result. Python commands are executed by the manifest runner as `python -B -m unittest <module>`; Node commands as `node <path>`.

| Test | Domain | Language / runner | Local status | CI workflow / job / path | Classification | Action |
|---|---|---|---|---|---|---|
| `test_derivatives_platform.py` | Derivatives quantitative unit suite | Python unittest | PASS | P1 Quant runner; also P2 `provenance-and-deterministic-regression` → Run unit, security, and E2E gates | CI_ENFORCED_DIRECT | Kept; included in frozen manifest |
| `regression/test_p0_quant_integrity.py` | Quantitative integrity | Python unittest | PASS | P1 Quant runner; also direct P2 release gate | CI_ENFORCED_DIRECT | Kept; existing direct path preserved |
| `regression/test_p0a_market_time_integrity.py` | Market-time and point-in-time integrity | Python unittest | PASS | P1 quality-gate → Quant runner | CI_ENFORCED_VIA_SUITE | Orphan wired into manifest |
| `regression/test_p0b_futures_asset_cost_model.js` | Futures asset cost model | Node | PASS | P1 quality-gate → Quant runner | CI_ENFORCED_VIA_SUITE | Orphan wired into manifest |
| `regression/test_p0b_futures_execution_costs.js` | Futures execution cost | Node | PASS | P1 quality-gate → Quant runner | CI_ENFORCED_VIA_SUITE | Orphan wired into manifest |
| `regression/test_p0b1_futures_backtest_cost_wiring.js` | Futures backtest cost wiring | Node | PASS | P1 quality-gate → Quant runner | CI_ENFORCED_VIA_SUITE | Orphan wired into manifest |
| `regression/test_p1_options_execution.js` | Options execution and next-bar semantics | Node | PASS | P1 Quant runner; also direct P2 release gate | CI_ENFORCED_DIRECT | Kept; existing direct path preserved |
| `regression/test_p1_options_liquidity.js` | Options liquidity and execution constraints | Node | PASS | P1 Quant runner; also direct P2 release gate | CI_ENFORCED_DIRECT | Kept; existing direct path preserved |
| `regression/test_p1_point_in_time.js` | Point-in-time strategy semantics | Node | PASS | P1 Quant runner; also direct P2 release gate | CI_ENFORCED_DIRECT | Kept; existing direct path preserved |
| `regression/test_p1_portfolio_historical_var.js` | Portfolio historical VaR and Expected Shortfall | Node | PASS | P1 quality-gate → Quant runner | CI_ENFORCED_VIA_SUITE | Orphan wired into manifest |
| `regression/test_p1_portfolio_risk_contribution.js` | Portfolio Euler risk contribution | Node | PASS | P1 quality-gate → Quant runner | CI_ENFORCED_VIA_SUITE | Orphan wired into manifest |
| `regression/test_p1c_sharpe_return_semantics.js` | Sharpe ratio and return semantics | Node | PASS | P1 quality-gate → Quant runner | CI_ENFORCED_VIA_SUITE | Orphan wired into manifest |
| `regression/test_p1d_decision_outcome_ledger.py` | Decision/Outcome alignment and quantitative ledger semantics | Python unittest | PASS | P1 quality-gate → Quant runner | CI_ENFORCED_VIA_SUITE | Orphan wired into manifest; uses temporary DB |
| `regression/test_p1d_p0b_cost_contract.py` | Frozen transaction-cost contract | Python unittest | PASS | P1 quality-gate → Quant runner | CI_ENFORCED_VIA_SUITE | Orphan wired into manifest |
| `regression/test_p1_02_scenario_weight_semantics.py` | Scenario-weight/probability semantic boundary | Python unittest | PASS | P1 quality-gate → Quant runner | CI_ENFORCED_VIA_SUITE | Orphan wired into manifest |
| `regression/test_options_strategy_analyzer.js` | Options strategy quantitative semantics | Node | PASS | P1 Quant runner; also direct P2 release gate | CI_ENFORCED_DIRECT | Kept; existing direct path preserved |
| `regression/test_p2_asset_cost_contract.js` | Asset-specific backtest cost contract | Node | PASS | P1 quality-gate → Quant runner | CI_ENFORCED_VIA_SUITE | Orphan wired; provenance mention was not execution |
| `regression/test_q2_backtest_methodology.js` | Chronological backtest methodology and signal timing | Node | PASS (focused check and full gate) | P1 quality-gate → Quant runner | CI_ENFORCED_VIA_SUITE | Historical orphan wired; fixture already supplies `TW_EQUITY` |
| `regression/test_q3_risk_metric.js` | Risk metric and performance ratio semantics | Node | PASS | P1 quality-gate → Quant runner | CI_ENFORCED_VIA_SUITE | Orphan wired into manifest |
| `regression/test_p2_01_decision_ledger.py` | Immutable Decision evidence contract | Python unittest | PASS | P1 quality-gate → Quant runner | CI_ENFORCED_VIA_SUITE | Orphan wired into manifest; uses temporary DB |
| `regression/test_p2_02_outcome_evaluation.py` | Matured Outcome and target semantics | Python unittest | PASS | P1 quality-gate → Quant runner | CI_ENFORCED_VIA_SUITE | Orphan wired into manifest; uses temporary DB |
| `regression/test_p2_03_probability_forecast.py` | Probability forecast contract and calibration semantics | Python unittest | PASS | P1 quality-gate → Quant runner | CI_ENFORCED_VIA_SUITE | Orphan wired into manifest; API/ledger DBs are temporary |
| `regression/test_p203_amendment_002_closure.py` | P2-03 frozen amendment and evidence closure | Python unittest | PASS | P1 quality-gate → Quant runner | CI_ENFORCED_VIA_SUITE | Orphan wired into manifest; uses isolated fixture |
| `regression/test_p203_historical_research_replay.py` | Historical as-of replay and leakage controls | Python unittest | PASS | P1 quality-gate → Quant runner | CI_ENFORCED_VIA_SUITE | Wired; prospective DB guard isolated to temp fixture |
| `regression/test_p203_historical_research_v1r1.py` | Historical research V1R1 replay semantics | Python unittest | PASS | P1 quality-gate → Quant runner | CI_ENFORCED_VIA_SUITE | Orphan wired into manifest |
| `regression/test_p203_prospective_evidence_runner.py` | Prospective evidence isolation and eligibility | Python unittest | PASS | P1 quality-gate → Quant runner | CI_ENFORCED_VIA_SUITE | Orphan wired into manifest; uses temporary DB |
| `regression/test_p203_source_provenance.py` | Forecast source provenance | Python unittest | PASS | P1 quality-gate → Quant runner | CI_ENFORCED_VIA_SUITE | Orphan wired into manifest; uses temporary DB |
| `regression/test_p203_tx_contract_roll_audit.py` | TX contract-roll data integrity for research samples | Python unittest | PASS | P1 quality-gate → Quant runner | CI_ENFORCED_VIA_SUITE | Orphan wired into manifest |
| `regression/test_p203_v1r1_diagnostic_audit.py` | V1R1 coefficient and calibration diagnostic | Python unittest | PASS | P1 quality-gate → Quant runner | CI_ENFORCED_VIA_SUITE | Orphan wired; outputs under `.tmp` and cleans fixtures |
| `regression/test_p203_v2_historical_development.py` | Historical development protocol and leakage controls | Python unittest | PASS | P1 quality-gate → Quant runner | CI_ENFORCED_VIA_SUITE | Orphan wired into manifest |
| `regression/test_p204_score_bucket_performance.py` | Score-bucket performance contract | Python unittest | PASS | P1 quality-gate → Quant runner | CI_ENFORCED_VIA_SUITE | Orphan wired; uses temporary DB |
| `regression/test_p205_regime_performance.py` | Frozen regime-conditioned performance semantics | Python unittest | PASS | P1 quality-gate → Quant runner | CI_ENFORCED_VIA_SUITE | Orphan wired; uses temporary DB fixtures |
| `regression/test_p301_walk_forward_validation.py` | P3-01 walk-forward validation pipeline | Python unittest | PASS | P1 quality-gate → Quant runner | CI_ENFORCED_VIA_SUITE | Orphan wired into manifest |
| `regression/test_p302_regime_conditioned_validation.py` | P3-02 regime-conditioned validation pipeline | Python unittest | PASS | P1 quality-gate → Quant runner | CI_ENFORCED_VIA_SUITE | Orphan wired into manifest |
| `regression/test_p303_net_expectancy_validation.py` | P3-03 net-expectancy validation pipeline | Python unittest | PASS | P1 quality-gate → Quant runner | CI_ENFORCED_VIA_SUITE | Orphan wired into manifest |
| `regression/test_p304_model_drift_validation.py` | P3-04 temporal drift validation pipeline | Python unittest | PASS | P1 quality-gate → Quant runner | CI_ENFORCED_VIA_SUITE | Orphan wired into manifest |
| `regression/test_q5_quant_math.js` | Decision quant math | Node | PASS | P1 quality-gate → Quant runner | CI_ENFORCED_VIA_SUITE | Moved from an in-job direct call to the single Quant runner |

## Adjacent numbered candidates classified OUT_OF_SCOPE

| Test | Classification | Reason |
|---|---|---|
| `regression/test_p1_01_data_quality_remediation.py` | OUT_OF_SCOPE | Data-quality evidence contract, not quantitative formulas or model correctness. |
| `regression/test_p1_03_risk_classification.py` | OUT_OF_SCOPE | Risk taxonomy labels; risk formulas are covered by VaR, risk contribution, and Q3 tests. |
| `regression/test_p1_04_no_trade_state.py` | OUT_OF_SCOPE | Decision state and no-trade gating, not quantitative calculation correctness. |
| `regression/test_p1_04_no_trade_ui_gates.js` | OUT_OF_SCOPE | Frontend state/UI behavior. |
| `regression/test_p2_artifact_hygiene.py` | OUT_OF_SCOPE | Repository artifact hygiene. |
| `regression/test_p2_backend_boundaries.py` | OUT_OF_SCOPE | Backend architecture boundary checks. |
| `regression/test_p2_frontend_contract.js` | OUT_OF_SCOPE | Frontend wiring and transport contract checks. |
| `regression/test_p2_release_provenance.py` | OUT_OF_SCOPE | Release evidence helper tests; command execution is stubbed and the tests do not run the referenced matrix. |
| `regression/test_q5_decision_quality.py` | OUT_OF_SCOPE | Data-quality status, coverage, and dimension semantics. |

## Historical Q2 finding

`regression/test_q2_backtest_methodology.js` now provides `assetClass: "TW_EQUITY"`, `securityType: "EQUITY"`, and a fixture instrument symbol to `buildBacktestLearningModel`. Its current local result is PASS. The existing assertions still require `signalTiming === "T close"`, `executionTiming === "T+1 open"`, chronological train/validation/test ordering, untouched test selection, and a positive round-trip cost. No Q2 business assertion or production fail-closed rule was changed in P4-04.

## CI coverage decisions

- Six tests already had direct invocations in `p2-release-provenance.yml`; those commands remain unchanged. The same tests also participate in the P1 Quant runner as part of its complete mandatory set. This is retained independent release-gate redundancy across separate workflows, not duplicate execution in one job.
- `test_q5_quant_math.js` was previously called separately in the P1 job; it now runs once through the Quant runner, removing duplicate execution in that job.
- P0 quantitative-integrity and P1-02 scenario-weight UI regressions still made assertions against `page-global-market-assethub.js` after P4-03 moved the wording into `page-global-market-derivatives.js`. Their source paths now follow the authoritative module; every assertion remains unchanged.
- The P2-03 historical replay test used to read and hash `data/p203-prospective-ledger.sqlite3`. Its guard now uses a temporary sentinel file at an isolated test root, preserving the no-touch assertion without opening the authoritative database.
- The 30 tests with no actual execution path at audit start are now reached by the explicit manifest runner; no tests were retired.
- Both P1 quality and P2 release workflows run on pull requests and pushes to `main`. Actual remote branch-protection required-check settings were not available locally and were not queried or changed.

## Scope and evidence limits

No production quantitative implementation, frozen model contract, target, feature, horizon, cost rule, expected value, database schema/data, API/visual baseline, or P4-01/P4-02/P4-03 implementation was changed. The historical replay DB guard now uses a temporary sentinel file rather than reading the authoritative prospective DB. The gate does not claim statistical validity or performance; it enforces the existing deterministic regression contracts.
