# Phase 1–4 Git Promotion Manifest

Owner authorization: Phase 1–4 accepted work promotion only.

## Governance decision

- Phase 1: P1-01 through P1-04 are CLOSED; the Project Owner adjudicates this promotion gate as SATISFIED. No synthetic aggregate closure is created.
- Phase 2: P2-01 through P2-05 are CLOSED; the Project Owner adjudicates this promotion gate as SATISFIED. No synthetic aggregate closure is created.
- Phase 3: CLOSED; frozen parent contract and formal closure identities verified before manifest creation.
- Phase 4: CLOSED; P4-01 through P4-04 contract, closure, and inventory identities verified before manifest creation.
- Evidence non-claims remain: probabilityLabelAllowed=false; predictive validity, profitability, trading edge, statistical significance, and model stability are NOT ESTABLISHED.
- Source promotion does not change evidence maturity, database contents, deployment state, or authorize a next phase.

## Inventory rules

This manifest inventories git diff --name-only plus git ls-files --others --exclude-standard before staging. Every modified or untracked path has a category, phase/node attribution, artifact type, and inclusion reason. Generated runtime outputs are separated and remain subject to the required locked build/runtime checks.

Excluded: none of the 154 reported modified/untracked paths. No .tmp, SQLite database, cache, log, backup, environment, credential, or secret path appears in this non-ignored Git status inventory. Ignored files are not included.

AMBIGUOUS PROMOTION FILES: 0

## Included paths

| Path | State before staging | Category | Phase/node | Artifact type | Inclusion reason |
|---|---|---|---|---|---|
| .github/workflows/p1-quality-gate.yml | tracked modified | PROMOTE_P4 | P4-04 | CI workflow/Quant manifest-runner/regression | Required accepted Quant regression inventory, runner, workflow integration, and invariant coverage. |
| app.py | tracked modified | PROMOTE_SHARED_PHASE_ARTIFACT | P1/P2/P4-01 (market_config: P4-03) | backend Python source | Accepted builder/fetcher ownership and P1/P2 API, quality, decision, risk, and ledger consumers. |
| bonds.html | tracked modified | PROMOTE_P4 | P4-02/P4-03 | frontend source/page/runtime wiring | Accepted explicit-input shared calculations, page module decomposition, or loader/cache-version wiring. |
| builders.py | tracked modified | PROMOTE_SHARED_PHASE_ARTIFACT | P1/P2/P4-01 (market_config: P4-03) | backend Python source | Accepted builder/fetcher ownership and P1/P2 API, quality, decision, risk, and ledger consumers. |
| common-runtime.min.js | tracked modified | GENERATED_RUNTIME_ARTIFACT | P4-02/P4-03 | generated runtime bundle/source map/lock manifest | Locked Classic/ESM runtime outputs needed for accepted source/runtime consistency; gated by TD-18/TD-02 checks. |
| common-runtime.min.js.map | tracked modified | GENERATED_RUNTIME_ARTIFACT | P4-02/P4-03 | generated runtime bundle/source map/lock manifest | Locked Classic/ESM runtime outputs needed for accepted source/runtime consistency; gated by TD-18/TD-02 checks. |
| derivatives-ai.html | tracked modified | PROMOTE_P4 | P4-02/P4-03 | frontend source/page/runtime wiring | Accepted explicit-input shared calculations, page module decomposition, or loader/cache-version wiring. |
| derivatives-analytics.html | tracked modified | PROMOTE_P4 | P4-02/P4-03 | frontend source/page/runtime wiring | Accepted explicit-input shared calculations, page module decomposition, or loader/cache-version wiring. |
| derivatives-assets.html | tracked modified | PROMOTE_P4 | P4-02/P4-03 | frontend source/page/runtime wiring | Accepted explicit-input shared calculations, page module decomposition, or loader/cache-version wiring. |
| derivatives-status-esm-loader.js | tracked modified | PROMOTE_P4 | P4-02/P4-03 | frontend source/page/runtime wiring | Accepted explicit-input shared calculations, page module decomposition, or loader/cache-version wiring. |
| derivatives-status.html | tracked modified | PROMOTE_P4 | P4-02/P4-03 | frontend source/page/runtime wiring | Accepted explicit-input shared calculations, page module decomposition, or loader/cache-version wiring. |
| derivatives/ai.py | tracked modified | PROMOTE_SHARED_PHASE_ARTIFACT | P1/P2/P4-01 (market_config: P4-03) | backend Python source | Accepted builder/fetcher ownership and P1/P2 API, quality, decision, risk, and ledger consumers. |
| derivatives/analytics.py | tracked modified | PROMOTE_SHARED_PHASE_ARTIFACT | P1/P2/P4-01 (market_config: P4-03) | backend Python source | Accepted builder/fetcher ownership and P1/P2 API, quality, decision, risk, and ledger consumers. |
| derivatives_store.py | tracked modified | PROMOTE_SHARED_PHASE_ARTIFACT | P1/P2/P4-01 (market_config: P4-03) | backend Python source | Accepted builder/fetcher ownership and P1/P2 API, quality, decision, risk, and ledger consumers. |
| docs/TD02_FULL_ESM_build_manifest_2026-09-01.json | tracked modified | PROMOTE_P4 | P4-03 | generated build manifest | Records accepted TD-02 ESM build identity and runtime wiring. |
| fetch_registry.py | tracked modified | PROMOTE_SHARED_PHASE_ARTIFACT | P1/P2/P4-01 (market_config: P4-03) | backend Python source | Accepted builder/fetcher ownership and P1/P2 API, quality, decision, risk, and ledger consumers. |
| fetchers.py | tracked modified | PROMOTE_SHARED_PHASE_ARTIFACT | P1/P2/P4-01 (market_config: P4-03) | backend Python source | Accepted builder/fetcher ownership and P1/P2 API, quality, decision, risk, and ledger consumers. |
| futures.html | tracked modified | PROMOTE_P4 | P4-02/P4-03 | frontend source/page/runtime wiring | Accepted explicit-input shared calculations, page module decomposition, or loader/cache-version wiring. |
| index.html | tracked modified | PROMOTE_P4 | P4-02/P4-03 | frontend source/page/runtime wiring | Accepted explicit-input shared calculations, page module decomposition, or loader/cache-version wiring. |
| international-finance.html | tracked modified | PROMOTE_P4 | P4-02/P4-03 | frontend source/page/runtime wiring | Accepted explicit-input shared calculations, page module decomposition, or loader/cache-version wiring. |
| js/page-global-market-assethub.js | tracked modified | PROMOTE_P4 | P4-02/P4-03 | frontend source/page/runtime wiring | Accepted explicit-input shared calculations, page module decomposition, or loader/cache-version wiring. |
| js/page-global-market-futures.js | tracked modified | PROMOTE_P4 | P4-02/P4-03 | frontend source/page/runtime wiring | Accepted explicit-input shared calculations, page module decomposition, or loader/cache-version wiring. |
| js/page-global-market-options.js | tracked modified | PROMOTE_P4 | P4-02/P4-03 | frontend source/page/runtime wiring | Accepted explicit-input shared calculations, page module decomposition, or loader/cache-version wiring. |
| js/page-home.js | tracked modified | PROMOTE_P4 | P4-02/P4-03 | frontend source/page/runtime wiring | Accepted explicit-input shared calculations, page module decomposition, or loader/cache-version wiring. |
| js/page-tw.js | tracked modified | PROMOTE_P4 | P4-02/P4-03 | frontend source/page/runtime wiring | Accepted explicit-input shared calculations, page module decomposition, or loader/cache-version wiring. |
| js/page-us.js | tracked modified | PROMOTE_P4 | P4-02/P4-03 | frontend source/page/runtime wiring | Accepted explicit-input shared calculations, page module decomposition, or loader/cache-version wiring. |
| js/render-shared.js | tracked modified | PROMOTE_P4 | P4-02/P4-03 | frontend source/page/runtime wiring | Accepted explicit-input shared calculations, page module decomposition, or loader/cache-version wiring. |
| js/shared-calc.js | tracked modified | PROMOTE_P4 | P4-02/P4-03 | frontend source/page/runtime wiring | Accepted explicit-input shared calculations, page module decomposition, or loader/cache-version wiring. |
| js/state.js | tracked modified | PROMOTE_P4 | P4-02/P4-03 | frontend source/page/runtime wiring | Accepted explicit-input shared calculations, page module decomposition, or loader/cache-version wiring. |
| js/stock-detail.js | tracked modified | PROMOTE_P4 | P4-02/P4-03 | frontend source/page/runtime wiring | Accepted explicit-input shared calculations, page module decomposition, or loader/cache-version wiring. |
| market-overview.html | tracked modified | PROMOTE_P4 | P4-02/P4-03 | frontend source/page/runtime wiring | Accepted explicit-input shared calculations, page module decomposition, or loader/cache-version wiring. |
| market-pulse-esm-loader.js | tracked modified | PROMOTE_P4 | P4-02/P4-03 | frontend source/page/runtime wiring | Accepted explicit-input shared calculations, page module decomposition, or loader/cache-version wiring. |
| market-pulse-esm.min.js | tracked modified | GENERATED_RUNTIME_ARTIFACT | P4-02/P4-03 | generated runtime bundle/source map/lock manifest | Locked Classic/ESM runtime outputs needed for accepted source/runtime consistency; gated by TD-18/TD-02 checks. |
| market-pulse-esm.min.js.map | tracked modified | GENERATED_RUNTIME_ARTIFACT | P4-02/P4-03 | generated runtime bundle/source map/lock manifest | Locked Classic/ESM runtime outputs needed for accepted source/runtime consistency; gated by TD-18/TD-02 checks. |
| market_config.py | tracked modified | PROMOTE_SHARED_PHASE_ARTIFACT | P1/P2/P4-01 (market_config: P4-03) | backend Python source | Accepted builder/fetcher ownership and P1/P2 API, quality, decision, risk, and ledger consumers. |
| news.html | tracked modified | PROMOTE_P4 | P4-02/P4-03 | frontend source/page/runtime wiring | Accepted explicit-input shared calculations, page module decomposition, or loader/cache-version wiring. |
| options.html | tracked modified | PROMOTE_P4 | P4-02/P4-03 | frontend source/page/runtime wiring | Accepted explicit-input shared calculations, page module decomposition, or loader/cache-version wiring. |
| precious-metals.html | tracked modified | PROMOTE_P4 | P4-02/P4-03 | frontend source/page/runtime wiring | Accepted explicit-input shared calculations, page module decomposition, or loader/cache-version wiring. |
| pwa.js | tracked modified | PROMOTE_P4 | P4-02/P4-03 | frontend source/page/runtime wiring | Accepted explicit-input shared calculations, page module decomposition, or loader/cache-version wiring. |
| regression/baseline/api/api__ai-analysis.json | tracked modified | PROMOTE_P1 | P1-01–P1-04 | API baseline/domain source/regression | Captures accepted quality coverage and decision, scenario, risk, and no-trade contracts. |
| regression/baseline/api/api__derivatives__v1-status.json | tracked modified | PROMOTE_P1 | P1-01–P1-04 | API baseline/domain source/regression | Captures accepted quality coverage and decision, scenario, risk, and no-trade contracts. |
| regression/baseline/api/api__global-market__options.json | tracked modified | PROMOTE_P1 | P1-01–P1-04 | API baseline/domain source/regression | Captures accepted quality coverage and decision, scenario, risk, and no-trade contracts. |
| regression/baseline/api/api__index.json | tracked modified | PROMOTE_P1 | P1-01–P1-04 | API baseline/domain source/regression | Captures accepted quality coverage and decision, scenario, risk, and no-trade contracts. |
| regression/baseline/api/api__options.json | tracked modified | PROMOTE_P1 | P1-01–P1-04 | API baseline/domain source/regression | Captures accepted quality coverage and decision, scenario, risk, and no-trade contracts. |
| regression/baseline/api/api__options__chain.json | tracked modified | PROMOTE_P1 | P1-01–P1-04 | API baseline/domain source/regression | Captures accepted quality coverage and decision, scenario, risk, and no-trade contracts. |
| regression/baseline/escapehtml_baseline.json | tracked modified | PROMOTE_P1 | P1-04 | regression baseline | Reconciles stale EscapeHtml exact-count baseline from 1891 to accepted P1-04 value 1907. |
| regression/td02_full_esm_wire.py | tracked modified | PROMOTE_P4 | P4-03 | build/runtime verification source or regression | Wires/verifies accepted module decomposition and generated asset versions. |
| regression/td18_minify_build.lock.json | tracked modified | GENERATED_RUNTIME_ARTIFACT | P4-02/P4-03 | generated runtime bundle/source map/lock manifest | Locked Classic/ESM runtime outputs needed for accepted source/runtime consistency; gated by TD-18/TD-02 checks. |
| regression/td18_shadow_build.lock.json | tracked modified | GENERATED_RUNTIME_ARTIFACT | P4-02/P4-03 | generated runtime bundle/source map/lock manifest | Locked Classic/ESM runtime outputs needed for accepted source/runtime consistency; gated by TD-18/TD-02 checks. |
| regression/td18_shadow_verify.py | tracked modified | PROMOTE_P4 | P4-03 | build/runtime verification source or regression | Wires/verifies accepted module decomposition and generated asset versions. |
| regression/test_derivatives_analytics_wiring.js | tracked modified | PROMOTE_P4 | P4-03 | build/runtime verification source or regression | Wires/verifies accepted module decomposition and generated asset versions. |
| regression/test_options_strategy_analyzer.js | tracked modified | PROMOTE_P4 | P4-03 | build/runtime verification source or regression | Wires/verifies accepted module decomposition and generated asset versions. |
| regression/test_p0_quant_integrity.py | tracked modified | PROMOTE_P4 | P4-04 | CI workflow/Quant manifest-runner/regression | Required accepted Quant regression inventory, runner, workflow integration, and invariant coverage. |
| regression/test_p0b1_futures_backtest_cost_wiring.js | tracked modified | PROMOTE_P4 | P4-04 | CI workflow/Quant manifest-runner/regression | Required accepted Quant regression inventory, runner, workflow integration, and invariant coverage. |
| regression/test_p1_options_execution.js | tracked modified | PROMOTE_SHARED_PHASE_ARTIFACT | P1/P2/P4-03 | regression test | Preserves P1/P2 semantics and ledger behavior through accepted P4 module ownership changes. |
| regression/test_p1_options_liquidity.js | tracked modified | PROMOTE_SHARED_PHASE_ARTIFACT | P1/P2/P4-03 | regression test | Preserves P1/P2 semantics and ledger behavior through accepted P4 module ownership changes. |
| regression/test_p1_point_in_time.js | tracked modified | PROMOTE_SHARED_PHASE_ARTIFACT | P1/P2/P4-03 | regression test | Preserves P1/P2 semantics and ledger behavior through accepted P4 module ownership changes. |
| regression/test_p1d_decision_outcome_ledger.py | tracked modified | PROMOTE_SHARED_PHASE_ARTIFACT | P1/P2/P4-03 | regression test | Preserves P1/P2 semantics and ledger behavior through accepted P4 module ownership changes. |
| regression/test_p2_frontend_contract.js | tracked modified | PROMOTE_SHARED_PHASE_ARTIFACT | P1/P2/P4-02/P4-03 | frontend regression test | Preserves decision semantics while checking accepted explicit-input and module-ownership changes. |
| regression/test_q2_backtest_methodology.js | tracked modified | PROMOTE_P4 | P4-04 | CI workflow/Quant manifest-runner/regression | Required accepted Quant regression inventory, runner, workflow integration, and invariant coverage. |
| regression/test_q5_decision_quality.py | tracked modified | PROMOTE_P1 | P1-01–P1-04 | API baseline/domain source/regression | Captures accepted quality coverage and decision, scenario, risk, and no-trade contracts. |
| regression/test_q5_quant_math.js | tracked modified | PROMOTE_P4 | P4-04 | CI workflow/Quant manifest-runner/regression | Required accepted Quant regression inventory, runner, workflow integration, and invariant coverage. |
| route-bundle.min.js | tracked modified | GENERATED_RUNTIME_ARTIFACT | P4-02/P4-03 | generated runtime bundle/source map/lock manifest | Locked Classic/ESM runtime outputs needed for accepted source/runtime consistency; gated by TD-18/TD-02 checks. |
| route-bundle.min.js.map | tracked modified | GENERATED_RUNTIME_ARTIFACT | P4-02/P4-03 | generated runtime bundle/source map/lock manifest | Locked Classic/ESM runtime outputs needed for accepted source/runtime consistency; gated by TD-18/TD-02 checks. |
| routes_derivatives.py | tracked modified | PROMOTE_SHARED_PHASE_ARTIFACT | P1/P2/P4-01 (market_config: P4-03) | backend Python source | Accepted builder/fetcher ownership and P1/P2 API, quality, decision, risk, and ledger consumers. |
| routes_system.py | tracked modified | PROMOTE_SHARED_PHASE_ARTIFACT | P1/P2/P4-01 (market_config: P4-03) | backend Python source | Accepted builder/fetcher ownership and P1/P2 API, quality, decision, risk, and ledger consumers. |
| routes_twse.py | tracked modified | PROMOTE_SHARED_PHASE_ARTIFACT | P1/P2/P4-01 (market_config: P4-03) | backend Python source | Accepted builder/fetcher ownership and P1/P2 API, quality, decision, risk, and ledger consumers. |
| service-worker.js | tracked modified | PROMOTE_P4 | P4-02/P4-03 | frontend source/page/runtime wiring | Accepted explicit-input shared calculations, page module decomposition, or loader/cache-version wiring. |
| td18-minify-bundle-manifest.json | tracked modified | GENERATED_RUNTIME_ARTIFACT | P4-02/P4-03 | generated runtime bundle/source map/lock manifest | Locked Classic/ESM runtime outputs needed for accepted source/runtime consistency; gated by TD-18/TD-02 checks. |
| test_derivatives_platform.py | tracked modified | PROMOTE_SHARED_PHASE_ARTIFACT | P1/P2/P4-01 | Python regression suite | Cross-phase derivatives regression coverage, including accepted builder/fetcher boundaries. |
| tw-Optional-stocks.html | tracked modified | PROMOTE_P4 | P4-02/P4-03 | frontend source/page/runtime wiring | Accepted explicit-input shared calculations, page module decomposition, or loader/cache-version wiring. |
| tw-etf.html | tracked modified | PROMOTE_P4 | P4-02/P4-03 | frontend source/page/runtime wiring | Accepted explicit-input shared calculations, page module decomposition, or loader/cache-version wiring. |
| tw-stock-search.html | tracked modified | PROMOTE_P4 | P4-02/P4-03 | frontend source/page/runtime wiring | Accepted explicit-input shared calculations, page module decomposition, or loader/cache-version wiring. |
| tw-stocks.html | tracked modified | PROMOTE_P4 | P4-02/P4-03 | frontend source/page/runtime wiring | Accepted explicit-input shared calculations, page module decomposition, or loader/cache-version wiring. |
| us-etf.html | tracked modified | PROMOTE_P4 | P4-02/P4-03 | frontend source/page/runtime wiring | Accepted explicit-input shared calculations, page module decomposition, or loader/cache-version wiring. |
| us-market-overview.html | tracked modified | PROMOTE_P4 | P4-02/P4-03 | frontend source/page/runtime wiring | Accepted explicit-input shared calculations, page module decomposition, or loader/cache-version wiring. |
| us-stock-search.html | tracked modified | PROMOTE_P4 | P4-02/P4-03 | frontend source/page/runtime wiring | Accepted explicit-input shared calculations, page module decomposition, or loader/cache-version wiring. |
| us-stocks.html | tracked modified | PROMOTE_P4 | P4-02/P4-03 | frontend source/page/runtime wiring | Accepted explicit-input shared calculations, page module decomposition, or loader/cache-version wiring. |
| us-watchlist.html | tracked modified | PROMOTE_P4 | P4-02/P4-03 | frontend source/page/runtime wiring | Accepted explicit-input shared calculations, page module decomposition, or loader/cache-version wiring. |
| derivatives/decision_state.py | untracked | PROMOTE_P2 | P2-01–P2-05 | Python domain/analysis source or regression | Implements/tests accepted P2 ledger, outcome, forecast, score-bucket, regime, and provenance work. |
| derivatives/model_drift_validation.py | untracked | PROMOTE_P3 | P3-01–P3-04 | Python validation source/regression | Implements/tests the frozen Phase 3 validation nodes. |
| derivatives/net_expectancy_validation.py | untracked | PROMOTE_P3 | P3-01–P3-04 | Python validation source/regression | Implements/tests the frozen Phase 3 validation nodes. |
| derivatives/probability_forecast.py | untracked | PROMOTE_P2 | P2-01–P2-05 | Python domain/analysis source or regression | Implements/tests accepted P2 ledger, outcome, forecast, score-bucket, regime, and provenance work. |
| derivatives/regime_conditioned_validation.py | untracked | PROMOTE_P3 | P3-01–P3-04 | Python validation source/regression | Implements/tests the frozen Phase 3 validation nodes. |
| derivatives/walk_forward_validation.py | untracked | PROMOTE_P3 | P3-01–P3-04 | Python validation source/regression | Implements/tests the frozen Phase 3 validation nodes. |
| docs/INVESTMENT_DECISION_EXECUTION_STATUS.md | untracked | PROMOTE_SHARED_PHASE_ARTIFACT | P1-01–P4-04 | governance documentation | Canonical accepted state and authoritative investment-decision scope. |
| docs/MARKET_PLATFORM_INVESTMENT_DECISION_AUDIT.md | untracked | PROMOTE_SHARED_PHASE_ARTIFACT | P1-01–P4-04 | governance documentation | Canonical accepted state and authoritative investment-decision scope. |
| docs/P2_03_FORMAL_CLOSURE.md | untracked | PROMOTE_P2 | P2-01–P2-05 | contract/closure documentation | Accepted P2 contracts, amendments, and engineering/governance closure evidence. |
| docs/P2_03_HISTORICAL_RESEARCH_FEATURE_CONTRACT_V1.md | untracked | PROMOTE_P2 | P2-01–P2-05 | contract/closure documentation | Accepted P2 contracts, amendments, and engineering/governance closure evidence. |
| docs/P2_03_PROTOCOL_AMENDMENT_002.md | untracked | PROMOTE_P2 | P2-01–P2-05 | contract/closure documentation | Accepted P2 contracts, amendments, and engineering/governance closure evidence. |
| docs/P2_03_RESEARCH_V2_PRE_REGISTRATION.md | untracked | PROMOTE_P2 | P2-01–P2-05 | contract/closure documentation | Accepted P2 contracts, amendments, and engineering/governance closure evidence. |
| docs/P2_03_RESEARCH_V2_PROTOCOL_AMENDMENT_001.md | untracked | PROMOTE_P2 | P2-01–P2-05 | contract/closure documentation | Accepted P2 contracts, amendments, and engineering/governance closure evidence. |
| docs/P2_04_FORMAL_CLOSURE.md | untracked | PROMOTE_P2 | P2-01–P2-05 | contract/closure documentation | Accepted P2 contracts, amendments, and engineering/governance closure evidence. |
| docs/P2_05_FORMAL_CLOSURE.md | untracked | PROMOTE_P2 | P2-01–P2-05 | contract/closure documentation | Accepted P2 contracts, amendments, and engineering/governance closure evidence. |
| docs/P2_05_REGIME_PERFORMANCE_CONTRACT.md | untracked | PROMOTE_P2 | P2-01–P2-05 | contract/closure documentation | Accepted P2 contracts, amendments, and engineering/governance closure evidence. |
| docs/P3_02_REGIME_CONDITIONED_VALIDATION_CONTRACT.md | untracked | PROMOTE_P3 | P3-01–P3-04 | contract/closure documentation | Frozen Phase 3 contract and accepted node/phase closure evidence. |
| docs/P3_03_FORMAL_CLOSURE.md | untracked | PROMOTE_P3 | P3-01–P3-04 | contract/closure documentation | Frozen Phase 3 contract and accepted node/phase closure evidence. |
| docs/P3_03_NET_EXPECTANCY_VALIDATION_CONTRACT.md | untracked | PROMOTE_P3 | P3-01–P3-04 | contract/closure documentation | Frozen Phase 3 contract and accepted node/phase closure evidence. |
| docs/P3_04_FORMAL_CLOSURE.md | untracked | PROMOTE_P3 | P3-01–P3-04 | contract/closure documentation | Frozen Phase 3 contract and accepted node/phase closure evidence. |
| docs/P3_04_MODEL_DRIFT_TEMPORAL_STABILITY_CONTRACT.md | untracked | PROMOTE_P3 | P3-01–P3-04 | contract/closure documentation | Frozen Phase 3 contract and accepted node/phase closure evidence. |
| docs/P4_01_BUILDERS_FETCHERS_DOMAIN_CONTRACT.md | untracked | PROMOTE_P4 | P4-01–P4-04 | contract/closure/inventory documentation | Accepted Phase 4 contracts, closures, quant inventory, and phase closure. |
| docs/P4_01_FORMAL_CLOSURE.md | untracked | PROMOTE_P4 | P4-01–P4-04 | contract/closure/inventory documentation | Accepted Phase 4 contracts, closures, quant inventory, and phase closure. |
| docs/P4_02_FORMAL_CLOSURE.md | untracked | PROMOTE_P4 | P4-01–P4-04 | contract/closure/inventory documentation | Accepted Phase 4 contracts, closures, quant inventory, and phase closure. |
| docs/P4_02_SHARED_CALC_HIDDEN_GLOBAL_STATE_CONTRACT.md | untracked | PROMOTE_P4 | P4-01–P4-04 | contract/closure/inventory documentation | Accepted Phase 4 contracts, closures, quant inventory, and phase closure. |
| docs/P4_03_FORMAL_CLOSURE.md | untracked | PROMOTE_P4 | P4-01–P4-04 | contract/closure/inventory documentation | Accepted Phase 4 contracts, closures, quant inventory, and phase closure. |
| docs/P4_03_GIANT_PAGE_MODULES_DECOMPOSITION_CONTRACT.md | untracked | PROMOTE_P4 | P4-01–P4-04 | contract/closure/inventory documentation | Accepted Phase 4 contracts, closures, quant inventory, and phase closure. |
| docs/P4_04_FORMAL_CLOSURE.md | untracked | PROMOTE_P4 | P4-01–P4-04 | contract/closure/inventory documentation | Accepted Phase 4 contracts, closures, quant inventory, and phase closure. |
| docs/P4_04_QUANT_CI_ORPHAN_REGRESSION_CONTRACT.md | untracked | PROMOTE_P4 | P4-01–P4-04 | contract/closure/inventory documentation | Accepted Phase 4 contracts, closures, quant inventory, and phase closure. |
| docs/P4_04_QUANT_REGRESSION_INVENTORY.md | untracked | PROMOTE_P4 | P4-01–P4-04 | contract/closure/inventory documentation | Accepted Phase 4 contracts, closures, quant inventory, and phase closure. |
| docs/PHASE3_FORMAL_CLOSURE.md | untracked | PROMOTE_P3 | P3-01–P3-04 | contract/closure documentation | Frozen Phase 3 contract and accepted node/phase closure evidence. |
| docs/PHASE3_MODEL_VALIDATION_CONTRACT.md | untracked | PROMOTE_P3 | P3-01–P3-04 | contract/closure documentation | Frozen Phase 3 contract and accepted node/phase closure evidence. |
| docs/PHASE4_FORMAL_CLOSURE.md | untracked | PROMOTE_P4 | P4-01–P4-04 | contract/closure/inventory documentation | Accepted Phase 4 contracts, closures, quant inventory, and phase closure. |
| js/page-global-market-asset-finance.js | untracked | PROMOTE_P4 | P4-02/P4-03 | frontend source/page/runtime wiring | Accepted explicit-input shared calculations, page module decomposition, or loader/cache-version wiring. |
| js/page-global-market-derivatives.js | untracked | PROMOTE_P4 | P4-02/P4-03 | frontend source/page/runtime wiring | Accepted explicit-input shared calculations, page module decomposition, or loader/cache-version wiring. |
| js/page-global-market-shared.js | untracked | PROMOTE_P4 | P4-02/P4-03 | frontend source/page/runtime wiring | Accepted explicit-input shared calculations, page module decomposition, or loader/cache-version wiring. |
| regression/quant_regression_manifest.json | untracked | PROMOTE_P4 | P4-04 | CI workflow/Quant manifest-runner/regression | Required accepted Quant regression inventory, runner, workflow integration, and invariant coverage. |
| regression/run_quant_regressions.py | untracked | PROMOTE_P4 | P4-04 | CI workflow/Quant manifest-runner/regression | Required accepted Quant regression inventory, runner, workflow integration, and invariant coverage. |
| regression/test_fetch_registry_bom.py | untracked | PROMOTE_P2 | P2-03 | regression test | Tests the accepted TAIFEX BOM/header recovery path. |
| regression/test_p1_01_data_quality_remediation.py | untracked | PROMOTE_P1 | P1-01–P1-04 | API baseline/domain source/regression | Captures accepted quality coverage and decision, scenario, risk, and no-trade contracts. |
| regression/test_p1_02_scenario_weight_semantics.py | untracked | PROMOTE_P1 | P1-01–P1-04 | API baseline/domain source/regression | Captures accepted quality coverage and decision, scenario, risk, and no-trade contracts. |
| regression/test_p1_03_risk_classification.py | untracked | PROMOTE_P1 | P1-01–P1-04 | API baseline/domain source/regression | Captures accepted quality coverage and decision, scenario, risk, and no-trade contracts. |
| regression/test_p1_04_no_trade_state.py | untracked | PROMOTE_P1 | P1-01–P1-04 | API baseline/domain source/regression | Captures accepted quality coverage and decision, scenario, risk, and no-trade contracts. |
| regression/test_p1_04_no_trade_ui_gates.js | untracked | PROMOTE_P1 | P1-01–P1-04 | API baseline/domain source/regression | Captures accepted quality coverage and decision, scenario, risk, and no-trade contracts. |
| regression/test_p203_amendment_002_closure.py | untracked | PROMOTE_P2 | P2-01–P2-05 | Python domain/analysis source or regression | Implements/tests accepted P2 ledger, outcome, forecast, score-bucket, regime, and provenance work. |
| regression/test_p203_historical_research_replay.py | untracked | PROMOTE_P2 | P2-01–P2-05 | Python domain/analysis source or regression | Implements/tests accepted P2 ledger, outcome, forecast, score-bucket, regime, and provenance work. |
| regression/test_p203_historical_research_v1r1.py | untracked | PROMOTE_P2 | P2-01–P2-05 | Python domain/analysis source or regression | Implements/tests accepted P2 ledger, outcome, forecast, score-bucket, regime, and provenance work. |
| regression/test_p203_prospective_evidence_runner.py | untracked | PROMOTE_P2 | P2-01–P2-05 | Python domain/analysis source or regression | Implements/tests accepted P2 ledger, outcome, forecast, score-bucket, regime, and provenance work. |
| regression/test_p203_source_provenance.py | untracked | PROMOTE_P2 | P2-01–P2-05 | Python domain/analysis source or regression | Implements/tests accepted P2 ledger, outcome, forecast, score-bucket, regime, and provenance work. |
| regression/test_p203_tx_contract_roll_audit.py | untracked | PROMOTE_P2 | P2-01–P2-05 | Python domain/analysis source or regression | Implements/tests accepted P2 ledger, outcome, forecast, score-bucket, regime, and provenance work. |
| regression/test_p203_v1r1_diagnostic_audit.py | untracked | PROMOTE_P2 | P2-01–P2-05 | Python domain/analysis source or regression | Implements/tests accepted P2 ledger, outcome, forecast, score-bucket, regime, and provenance work. |
| regression/test_p203_v2_historical_development.py | untracked | PROMOTE_P2 | P2-01–P2-05 | Python domain/analysis source or regression | Implements/tests accepted P2 ledger, outcome, forecast, score-bucket, regime, and provenance work. |
| regression/test_p204_score_bucket_performance.py | untracked | PROMOTE_P2 | P2-01–P2-05 | Python domain/analysis source or regression | Implements/tests accepted P2 ledger, outcome, forecast, score-bucket, regime, and provenance work. |
| regression/test_p205_regime_performance.py | untracked | PROMOTE_P2 | P2-01–P2-05 | Python domain/analysis source or regression | Implements/tests accepted P2 ledger, outcome, forecast, score-bucket, regime, and provenance work. |
| regression/test_p2_01_decision_ledger.py | untracked | PROMOTE_P2 | P2-01–P2-05 | Python domain/analysis source or regression | Implements/tests accepted P2 ledger, outcome, forecast, score-bucket, regime, and provenance work. |
| regression/test_p2_02_outcome_evaluation.py | untracked | PROMOTE_P2 | P2-01–P2-05 | Python domain/analysis source or regression | Implements/tests accepted P2 ledger, outcome, forecast, score-bucket, regime, and provenance work. |
| regression/test_p2_03_probability_forecast.py | untracked | PROMOTE_P2 | P2-01–P2-05 | Python domain/analysis source or regression | Implements/tests accepted P2 ledger, outcome, forecast, score-bucket, regime, and provenance work. |
| regression/test_p301_walk_forward_validation.py | untracked | PROMOTE_P3 | P3-01–P3-04 | Python validation source/regression | Implements/tests the frozen Phase 3 validation nodes. |
| regression/test_p302_regime_conditioned_validation.py | untracked | PROMOTE_P3 | P3-01–P3-04 | Python validation source/regression | Implements/tests the frozen Phase 3 validation nodes. |
| regression/test_p303_net_expectancy_validation.py | untracked | PROMOTE_P3 | P3-01–P3-04 | Python validation source/regression | Implements/tests the frozen Phase 3 validation nodes. |
| regression/test_p304_model_drift_validation.py | untracked | PROMOTE_P3 | P3-01–P3-04 | Python validation source/regression | Implements/tests the frozen Phase 3 validation nodes. |
| regression/test_p401_builders_fetchers_domain.py | untracked | PROMOTE_P4 | P4-04 | CI workflow/Quant manifest-runner/regression | Required accepted Quant regression inventory, runner, workflow integration, and invariant coverage. |
| regression/test_p402_shared_calc_hidden_global_state.js | untracked | PROMOTE_P4 | P4-04 | CI workflow/Quant manifest-runner/regression | Required accepted Quant regression inventory, runner, workflow integration, and invariant coverage. |
| regression/test_p403_giant_page_modules_decomposition.js | untracked | PROMOTE_P4 | P4-04 | CI workflow/Quant manifest-runner/regression | Required accepted Quant regression inventory, runner, workflow integration, and invariant coverage. |
| regression/test_p404_quant_ci_coverage.py | untracked | PROMOTE_P4 | P4-04 | CI workflow/Quant manifest-runner/regression | Required accepted Quant regression inventory, runner, workflow integration, and invariant coverage. |
| risk_taxonomy.py | untracked | PROMOTE_P1 | P1-01–P1-04 | API baseline/domain source/regression | Captures accepted quality coverage and decision, scenario, risk, and no-trade contracts. |
| scripts/p203_historical_research_replay.py | untracked | PROMOTE_P2 | P2-01–P2-05 | Python domain/analysis source or regression | Implements/tests accepted P2 ledger, outcome, forecast, score-bucket, regime, and provenance work. |
| scripts/p203_historical_research_v1r1_replay.py | untracked | PROMOTE_P2 | P2-01–P2-05 | Python domain/analysis source or regression | Implements/tests accepted P2 ledger, outcome, forecast, score-bucket, regime, and provenance work. |
| scripts/p203_p2_03_closure_manifest.py | untracked | PROMOTE_P2 | P2-01–P2-05 | Python domain/analysis source or regression | Implements/tests accepted P2 ledger, outcome, forecast, score-bucket, regime, and provenance work. |
| scripts/p203_prospective_evidence_runner.py | untracked | PROMOTE_P2 | P2-01–P2-05 | Python domain/analysis source or regression | Implements/tests accepted P2 ledger, outcome, forecast, score-bucket, regime, and provenance work. |
| scripts/p203_roll_continuity_feasibility_audit.py | untracked | PROMOTE_P2 | P2-01–P2-05 | Python domain/analysis source or regression | Implements/tests accepted P2 ledger, outcome, forecast, score-bucket, regime, and provenance work. |
| scripts/p203_tx_contract_roll_audit.py | untracked | PROMOTE_P2 | P2-01–P2-05 | Python domain/analysis source or regression | Implements/tests accepted P2 ledger, outcome, forecast, score-bucket, regime, and provenance work. |
| scripts/p203_v1r1_diagnostic_audit.py | untracked | PROMOTE_P2 | P2-01–P2-05 | Python domain/analysis source or regression | Implements/tests accepted P2 ledger, outcome, forecast, score-bucket, regime, and provenance work. |
| scripts/p203_v2_historical_development.py | untracked | PROMOTE_P2 | P2-01–P2-05 | Python domain/analysis source or regression | Implements/tests accepted P2 ledger, outcome, forecast, score-bucket, regime, and provenance work. |
| scripts/p204_score_bucket_performance.py | untracked | PROMOTE_P2 | P2-01–P2-05 | Python domain/analysis source or regression | Implements/tests accepted P2 ledger, outcome, forecast, score-bucket, regime, and provenance work. |
| scripts/p205_regime_performance.py | untracked | PROMOTE_P2 | P2-01–P2-05 | Python domain/analysis source or regression | Implements/tests accepted P2 ledger, outcome, forecast, score-bucket, regime, and provenance work. |
| docs/PHASE1_4_GIT_PROMOTION_MANIFEST.md | untracked (created for this promotion) | PROMOTE_SHARED_PHASE_ARTIFACT | Phase 1–4 | governance manifest | Required by Owner authorization; freezes the exact promotion path set. |

## Excluded paths

None. Excluded untracked or sensitive local artifacts were not present in the non-ignored Git status inventory.

## Count

- Existing modified tracked paths: 79
- Existing untracked paths: 76
- Manifest path added by this promotion: 1
- Intended staged paths: 156

Staging is authorized only for the exact included paths in this manifest, and only after all required verification gates pass.

## Whitespace audit

- The untracked-file scan found 27 trailing-whitespace instances, all exactly two ASCII spaces on Markdown quote-continuation or metadata lines; they are retained as Markdown hard breaks.
- The staged diff check also identifies the final blank line in docs/PHASE3_MODEL_VALIDATION_CONTRACT.md. The contract remains byte-identical to the Owner-authorized SHA-256 43ebcad66cd8267c07bca2419fbbcdeca066e6195eecf1e4ac782fd5954bbc57 and its accepted closure record; it was not normalized or edited.
- No unclassified whitespace issue was found.
