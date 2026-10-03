# P4-04 Quant CI / Orphan Regression Contract

**Contract ID:** `P4_04_QUANT_CI_ORPHAN_REGRESSION_V1`  
**Status:** FROZEN BEFORE IMPLEMENTATION  
**Date:** 2026-10-03

## Scope

P4-04 inventories quantitative correctness regressions, traces their actual local and CI execution paths, classifies adjacent candidates, fixes only test isolation or CI coverage defects, and makes every mandatory quant test discoverable through one deterministic local/CI entrypoint.

The current repository has four GitHub Actions workflows and no existing P4-04 contract or canonical Quant runner. The authoritative deterministic entrypoint will be `regression/run_quant_regressions.py`, driven by `regression/quant_regression_manifest.json`. It will be invoked by the existing `.github/workflows/p1-quality-gate.yml` `quality-gate` job, which runs for pull requests and pushes to `main`. No new workflow, npm dependency, or remote branch-protection change is in scope.

The fixed initial inventory is 37 quant test files: 25 Python unittest modules and 12 Node regression scripts. The machine-readable manifest is the only runner membership source. A separate coverage regression will detect unclassified numbered quant-test candidates and ensure the manifest, inventory document, runner, and workflow stay connected. Nine adjacent numbered tests reviewed as non-quantitative remain explicitly classified `OUT_OF_SCOPE` in the inventory artifact.

## Quant-test definition

In scope are regressions whose protected behavior materially concerns:

- backtest timing, chronological splits, execution, and transaction costs;
- quantitative risk measures, Sharpe/return semantics, VaR, Expected Shortfall, and risk contribution;
- point-in-time and Decision/Outcome semantics required for quantitative evaluation;
- probability forecast/calibration contracts, score-bucket and regime performance;
- walk-forward, regime-conditioned, net-expectancy, and temporal-drift validation;
- quantitative strategy calculations and frozen scenario-weight/probability boundaries.

Data-quality-only, risk-taxonomy-only, no-trade state/UI, build/provenance, frontend-contract, and repository-hygiene tests are not quantitative regressions for this inventory. They remain owned by their existing tests/workflows.

## Classification taxonomy

Every in-scope test receives exactly one classification:

- `CI_ENFORCED_DIRECT`: a CI workflow explicitly invokes the test.
- `CI_ENFORCED_VIA_SUITE`: the deterministic Quant runner invokes it from the frozen manifest.
- `LOCAL_ONLY_VALID`: valid and relevant, intentionally excluded from required CI with a documented reason.
- `ORPHAN`: valid/relevant, with no authoritative CI execution path or approved exclusion.
- `SUPERSEDED_CANDIDATE`: possible replacement exists, but retirement is not yet proven.
- `INVALID / BROKEN`: cannot exercise the current frozen contract correctly.
- `OUT_OF_SCOPE`: reviewed adjacent candidate that does not protect quantitative correctness.

No test may be retired without the invariant-to-replacement-to-CI evidence required by the P4-04 authorization. Uncertain tests remain present. A test merely referenced by provenance metadata is not considered executed unless an actual workflow command reaches it.

## Runner and CI policy

The JSON manifest freezes test membership and commands. The runner must:

- run from the repository root, locally and in CI, with deterministic manifest order;
- execute Python unittest modules with bytecode generation disabled and Node scripts through the configured Node runtime;
- provide temporary DB/cache environment paths and never open or mutate the authoritative Decision/Outcome database;
- contain no mandatory live-provider/network test;
- stop on the first non-zero result and return that child's non-zero exit code to the workflow;
- report the script count, per-script command/status, elapsed time, and test counts only when the child runner exposes them.

The coverage regression must validate the contract identity, exact manifest membership, file existence, single classification, inventory documentation coverage, runner consumption, workflow invocation, and failure propagation using a controlled temporary child process. It must not use GitHub network access.

The existing P2 release-provenance workflow retains its present direct P0/P1 execution path. Overlap with the new Quant runner across these separate workflows is documented as independent release-gate redundancy; redundant execution within the P1 quality-gate job must be removed when tests move under the runner.

## Q2 fixture and failure policy

`regression/test_q2_backtest_methodology.js` must retain explicit `assetClass: "TW_EQUITY"` and its existing `signalTiming`, `executionTiming`, chronological split, effective-sample, and cost assertions. Production fail-closed cost semantics and quantitative calculations must not be changed to satisfy a fixture.

No assertion may be removed or weakened to obtain a pass. If a valid regression reveals a production quantitative defect, P4-04 blocks and no model/production formula is changed under this contract. Stale CI references must be resolved. Workflow commands must fail on mandatory test failure; no `continue-on-error`, ignored return code, or shell `|| true` is permitted.

## Workflow and compatibility boundaries

The P1 quality-gate workflow may be minimally edited to call the runner and coverage regression. Workflow YAML, paths, working directory, and non-zero failure behavior must be locally validated. Remote branch protection is not inspected or modified; report only workflow triggers and local evidence.

P4-01, P4-02, and P4-03 implementation semantics remain unchanged. Their compatibility guards are run locally during P4-04 verification. No visual baselines, API baselines, frontend runtime bundles, model contracts, formulas, target/features/horizons, database schemas, authoritative DB data, or remote settings may be changed.

## Acceptance criteria

P4-04 Engineering PASS requires:

1. This frozen contract and deterministic inventory exist.
2. Every in-scope quant regression is listed and classified exactly once; every adjacent candidate exclusion has a reason.
3. Every mandatory quant regression has an actual deterministic workflow path through the manifest-driven runner or a direct workflow invocation.
4. No valid mandatory quant regression remains orphaned; no test is retired without full supersession proof.
5. The Q2 fixture is valid and passes without changing business assertions or production semantics.
6. Authoritative DB data is untouched and the mandatory test set has no live-provider dependency.
7. The runner and structural coverage regression pass locally; a controlled child failure proves non-zero propagation.
8. Workflow syntax, script paths, and working directory are validated locally.
9. P4-01/P4-02/P4-03 remain CLOSED; `git diff --check` passes; no Git promotion or deployment occurs.
10. No known unresolved P4-04 correctness or coverage defect remains.

Successful execution records `P4-04: EXECUTION COMPLETE`, `ENGINEERING: PASS`, and `FORMAL ACCEPTANCE: PENDING PROJECT OWNER`. It does not close P4-04 or Phase 4.

## Non-goals

No model redesign, production quantitative behavior change, CI modernization program, workflow proliferation, remote branch-protection edit, broad test renaming/deletion, unrelated refactor, Phase 4 formal closure, Git promotion, deployment, or next-phase work is authorized.
