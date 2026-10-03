# CANONICAL STATUS RECORD

This document is the canonical execution-status record for the Investment Decision Optimization workstream.

It records the current authorized node states for P1-01 through P1-04 and P2 through P4. If another document conflicts with a node status here, the Project Owner's latest explicit authorization and the latest status in this document govern. This record does not overwrite or amend other historical governance documents.

**Project Owner is the sole decision authority for closure and authorization of next steps.**

## P1-01 — Data Quality Coverage

```text
STATUS: CLOSED

Remediation: PASS
Live Verification: PARTIAL
Acceptance: PASS
Acceptance Readiness: READY
Formal Closure: APPROVED BY PROJECT OWNER
```

Completed remediation and acceptance included Yahoo market-date integrity; TAIFEX provider-failure and stale-cache quality evidence; distinction among Primary, Supplement, Explicit Yahoo, Automatic Fallback, Cache, and UNKNOWN roles; machine-readable Quality Coverage, Dimensions, Status, and Source Provenance; API-to-Ledger provenance round trip; and confirmation that Market Score, Risk Score, Strategy Suggestion, and the existing `fallbackSource=50` score mapping had no unintended change.

Residual Live Evidence:

```text
- Auto Fallback: NOT OBSERVED
- Provider Failure: NOT OBSERVED
- Stale Cache: NOT OBSERVED
- Yahoo OI Supplement: NOT OBSERVED
```

These residual live-observation gaps did not block closure because they were not mandatory conditions of the original P1-01 Acceptance Gate. Live Verification remains PARTIAL and is not upgraded to PASS by formal closure.

P1-01 source snapshots:

```text
Runtime Snapshot SHA-256:
3fe9fba58218cc98c1c8ac70e2da4602dfecab0c6f23d0e759bdd600c41ada96

Test Snapshot SHA-256:
6860e64f2b294576eccc826ffb2ea9601e8bdff9bce936b69d1c2f2b73b3ba47
```

These snapshot hashes identify source snapshots; they are not Git commit hashes.

## P1-02 — Scenario Weight

```text
STATUS: CLOSED

Implementation: COMPLETE
Semantic Regression: PASS
Numeric Compatibility: PASS
ESM Wiring: PASS
Visual Verification: PASS — PRE-EXISTING
Overall: PASS
Formal Closure: APPROVED BY PROJECT OWNER
```

The user-facing and machine-readable semantics distinguish:

```text
Scenario Weight != Probability
Scenario Weight != Win Rate
Scenario Weight != Expected Return
Scenario Weight != Confidence Probability
```

For scenarios without formal calibration evidence, `probabilityLabelAllowed` remains `false`. The legacy `probabilities` field remains as a deprecated compatibility field; canonical consumers use `scenarioWeights`.

Numeric compatibility was accepted with no unintended change to Scenario Weight formula or normalization, Market Score, Risk Score, Strategy Suggestion, Backtest, or Expected Return.

P1-02 visual residual:

```text
derivatives-status.html retains a pre-existing 13.806% difference against the existing visual baseline.
This issue is not attributable to P1-02.

Pure HEAD vs existing baseline:
13.806%

P1-02 candidate vs existing baseline:
13.806%

Pure HEAD vs candidate:
0.0000%
```

Pure HEAD and candidate screenshots have the same SHA-256:

```text
4435a5d61894aa9ae64fdc00d8876bb65c364f00c0a05ba7b580cf94f9ccd9df
```

DOM counts matched (6 cards, 13 table rows, 0 canvas), and page-text SHA-256 matched:

```text
ad136839c1376d5156fd52e65f3441974a6b0006e4380333dcf0006de83e67ef
```

`derivatives-status.html` is not a Scenario Weight consumer. The visual finding is a pre-existing rendering/baseline difference, not caused by P1-02. This record does not declare the existing visual baseline healthy.

## P1-03 — Risk Score Classification
`	ext
STATUS: CLOSED

Implementation / Verification: PASS
Risk Taxonomy: PASS
Numeric Compatibility: PASS
API / Frontend / Ledger Classification: PASS
Formal Closure: APPROVED BY PROJECT OWNER
`

Canonical risk taxonomy:

`	ext
MARKET_RISK
SIGNAL_RISK
STRATEGY_RISK
PORTFOLIO_RISK
UNKNOWN
`

Risk scores with the same numeric value retain distinct risk semantics and are comparable only within the same risk type. API, Frontend, and Decision Ledger preserve the classification. Options Market Risk and Strategy Risk are distinguished; Signal Risk remains separate from Data Quality. Portfolio Risk retains its existing VaR, ES, Concentration, and Risk Contribution semantics. Legacy numeric scores remain compatible. Unclassifiable items use UNKNOWN. No Overall Risk aggregation formula or existing Risk Formula was redesigned.

Recorded verification evidence (completed before this closure; not rerun during Formal Closure):

`	ext
P1-03 + P1D Ledger + Q5 regression: 34 tests PASS
Derivatives Platform: 206 tests PASS
Portfolio Risk Contribution: 12 cases PASS
Portfolio Historical VaR / ES: 12 checks PASS
Q5 Quant Math: PASS
Derivatives API Transport / Runtime Dispatch: 3 tests PASS
Python Syntax: PASS
Changed JS Syntax: PASS
ESM Wiring: PASS — 21 pages
Runtime Loader: PASS — 21/21
TD-18 Minify / Shadow Checks: PASS — 3 bundles / 895 symbols / no missing symbols
Quick Baseline: PASS
Interaction Compare: PASS — 94/94
git diff --check: PASS
`

Visual Residual:

`	ext
derivatives-status.html retains the known pre-existing 13.806% visual baseline difference.
No evidence attributes this difference to P1-03.
Status: PRE-EXISTING / NOT ATTRIBUTABLE TO P1-03
Screenshot SHA-256: 4435a5d61894aa9ae64fdc00d8876bb65c364f00c0a05ba7b580cf94f9ccd9df
This hash matches the P1-02 Pure HEAD and Candidate screenshots.
Full frontend visual suite: NOT PASS (20 pages had external font/network noise; one page retained the known visual residual).
`

Formal closure is limited to P1-03 and does not authorize P1-04 or any later node.


## P1-04 — No-Trade State

```text
STATUS: CLOSED

Implementation:
COMPLETE

Core Regression:
PASS

Decision Contract:
PASS

Ledger / Outcome Isolation:
PASS

Numeric Compatibility:
PASS

escapeHtml Attribution:
PASS

Quick Baseline Mechanical Result:
FAIL — escapeHtml exact-count baseline mismatch (1907 vs 1891)

Security / Semantic Attribution:
PASS

Classification:
EXPECTED P1-04 SECURITY COUNT DELTA

Baseline:
UNCHANGED

Visual Attribution:
PASS — PRE-EXISTING / NOT ATTRIBUTABLE TO P1-04

Visual Residual:
derivatives-status.html retains the known 13.806% difference against the existing visual baseline.
P1-03 historical and P1-04 screenshot SHA-256 are identical:
4435a5d61894aa9ae64fdc00d8876bb65c364f00c0a05ba7b580cf94f9ccd9df
DOM counts and page text SHA-256 are unchanged.
The full frontend visual suite is not declared PASS.

Re-Verification:
PASS

Formal Closure:
APPROVED BY PROJECT OWNER
```

## P2-01 — Decision Ledger

```text
STATUS: CLOSED

Implementation:
COMPLETE

Decision Ledger Contract:
PASS

Historical Snapshot Stability:
PASS

Round Trip:
PASS

Data Quality / Provenance Persistence:
PASS

Scenario Semantics Persistence:
PASS

Risk Classification Persistence:
PASS

Decision State Persistence:
PASS

Outcome Isolation:
PASS

Duplicate / Retry Semantics:
PASS

Numeric Compatibility:
PASS

DB Schema Change:
NO

Formal Closure:
APPROVED BY PROJECT OWNER

Existing Decision Ledger:
EXTENDED / HARDENED

Decision Ledger Schema:
P2_01_DECISION_LEDGER_V1 (JSON metadata)

Decision Snapshot API:
PASS — GET /api/decision-ledger/<decision_id>

Quick Baseline Mechanical Result:
FAIL — escapeHtml exact-count baseline mismatch (1907 vs 1891)
P2-01 changed no frontend source; the known P1-04 delta remains attributed and the baseline is unchanged.

P2-01 Quick Baseline Impact:
NO NEW DELTA
```

## P2-02 — Outcome Evaluation

```text
STATUS: CLOSED
AUTHORIZATION: APPROVED BY PROJECT OWNER
Implementation: COMPLETE
Outcome Evaluation Contract: PASS
Point-in-Time Safety: PASS
Timestamp Integrity: PASS
Outcome Status Semantics: PASS
Decision State Semantics: PASS
Directional / Strategy Return Separation: PASS
Outcome Provenance: PASS
Decision Snapshot Isolation: PASS
Retry / Conflict Semantics: PASS
Multi-Horizon Isolation: PASS
Numeric Compatibility: PASS
Database Schema Change: NO
Formal Closure: APPROVED BY PROJECT OWNER
```

Outcome records use the existing `decision_outcome` table and versioned JSON metadata. The contract distinguishes EVALUATED, PENDING, NOT_APPLICABLE, UNAVAILABLE, and INVALID; keeps directional return separate from supported frozen futures cost results; persists explicit entry/evaluation references, timestamps, and provenance; and rejects conflicting retries for the same decision/horizon. T+N is defined as observed market sessions, with horizon maturity supplied explicitly when a caller knows a horizon is not mature; no exchange calendar or maturity is inferred from wall-clock days.

Recorded verification evidence (completed before Formal Closure; not rerun during closure):

```text
Combined required Python suite: 294 tests PASS
P2-02 dedicated regression: PASS — 12 cases
Derivatives Platform: PASS
P2-01 Decision Ledger compatibility: PASS
P1-01 through P1-04 compatibility: PASS
Q5 Decision Quality: PASS
P0-B Cost Contract: PASS
API Transport: DERIVATIVES_API_TRANSPORT_OK
Python AST syntax: PASS
git diff --check: PASS
```

Quick Baseline remains mechanically FAIL because the pre-existing P1-04 `escapeHtml` exact-count delta is 1907 vs 1891. Attribution remains PASS as the expected P1-04 security count delta. P2-02 changed no frontend source, added no escapeHtml delta, and changed no baseline. API contract checks in Quick Baseline passed; P2-02 Quick Baseline Impact: NO NEW DELTA.

Residual risks (non-blocking):

```text
- Outcome evaluation depends on callers supplying trustworthy future observations.
- Outcome provenance may remain UNKNOWN when caller/provider evidence is unavailable.
- No exchange-calendar service was added.
- No automatic outcome evaluator or scheduler was added.
- No full outcome correction/version-history subsystem was added.
```

## P2-03 — OOS Calibration

```text
STATUS: BLOCKED
AUTHORIZATION: APPROVED BY PROJECT OWNER
Probability Forecast Foundation: PASS
Eligible Probability Signal Contract: FOUND
OOS Calibration History: INSUFFICIENT / NOT OBSERVED
Blocker: INSUFFICIENT OOS CALIBRATION HISTORY
```

The P2-03 blocker remediation added an independent prospective forecast contract:

```text
Target: DIRECTIONAL_SUCCESS = 1 when P2-02 decisionAlignedReturn > 0; 0 when < 0; flat excluded.
Target contract: P2_03_DIRECTIONAL_SUCCESS_V1
Horizon: T+1 observed market session
Feature contract: P2_03_DERIVATIVES_SCORE_FEATURES_V1
Model: deterministic standard-library logistic regression; model version fingerprints training samples and fitted coefficients.
Forecast persistence: immutable Decision Ledger decision_output JSON; PROSPECTIVE_ONLY.
probabilityLabelAllowed: false
```

Training uses only earlier, same-instrument `EVALUATED` P2-02 outcomes whose target, horizon, outcome contract, decision state, source timestamps, and decision-time features pass validation. Every fit cutoff is earlier than the forecast decision time. Forecast generation fails closed until at least 30 eligible training records and both target classes exist. Historical decisions without a persisted forecast are never backfilled; replayed decisions retain their original immutable snapshot. Heuristic scores are model features only and are not directly converted into probability. P1-02 scenario semantics and all existing trading, risk, and outcome fields remain separate.

The selected prospective horizon is the shortest explicitly supported observed-session horizon (`T+1`), avoiding performance-based horizon selection. Actual persisted outcome-horizon counts were not inspected because project instructions prohibit reading the SQLite database. No repository document reports those counts; therefore `T+1` is not claimed to be the historical maximum-sample horizon. No live forecast or historical OOS pair was observed in this run. Historical forecasts are `HISTORICAL_FORECAST_NOT_AVAILABLE`; the isolated regression fixtures are not calibration evidence. The existing calibration helper remains fail-closed and no OOS metrics were claimed.

Verification: 6 dedicated P2-03 tests passed; 290 related Python regression tests passed; Python syntax checks passed. Quick Baseline remains failed on the pre-existing security count (`escapeHtml` 1907 vs 1891, expected P1-04 delta); no baseline was changed. Foundation and Ledger round-trip were tested with an isolated temporary database only. P2-03 remains blocked until prospective forecasts mature into sufficient, valid chronological OOS calibration evidence.

Blocker remediation audit: repository search found no existing probability-producing model or `predict_proba` wiring. The P2-02 outcome contract records continuous directional/strategy returns over `T+N` observed market sessions; it does not define a fixed binary event target. Defining an event such as positive net return would add target semantics not present in the approved outcome contract. Decision Ledger stores decision-time inputs and immutable outputs, but no decision-time probability forecast; historical forecast reconstruction is therefore unavailable. No heuristic-to-probability transformation, new predictive model, Ledger field, schema change, or calibration metric was added. P2-03 remains BLOCKED with `probabilityLabelAllowed: false`.

### P2-03 Prospective OOS Evidence Capture Foundation (2026-10-01)

Foundation: `PASS`. A local non-production, prospective-only SQLite evidence database is initialized at `data/p203-prospective-ledger.sqlite3`; its manifest labels it `P2_03_EVIDENCE_CAPTURE`, and SQLite `application_id` is `P203` (`0x50323033`). It uses the existing schema with no migration or new tables. `DERIVATIVES_DB_PATH` is set only for the runner process; no permanent environment or production configuration changed. Initial setup counts were `decision_ledger=0` and `decision_outcome=0`; no fixture or synthetic rows were written to this evidence database. The cold-start regressions keep forecasts unavailable until eligible history exists and keep `probabilityLabelAllowed=false`.

Prospective capture (2026-10-02): `REAL PROVIDER-BACKED CAPTURE: OBSERVED` through the existing TX analysis path. TAIFEX is identified in the persisted input snapshot as the primary futures source (`DailyMarketReportFut`); a Yahoo futures quote source is also present as an analysis input. One decision was persisted (`cd5434d8bf864e83a9eaf22382b859ee0d89a6da247d837ef968825935ff7267`, `market_as_of=2026-10-01`, `data_as_of=2026-10-01`). It is `NO_TRADE`, `decisionEligible=false`; forecast is null with `UNAVAILABLE_INELIGIBLE_DECISION`, and `probabilityLabelAllowed=false`. Quality is `PARTIAL`, coverage 40, with completeness 50 and providerHealth 100. The existing Ledger row has `source_provenance=null`; the input snapshot identifies provider sources, but the normalized provenance field did not survive into this decision record. This is recorded as an evidence/provenance gap; the immutable row was not altered. No prior due decisions existed, no T+1 outcome was persisted, and valid prospective OOS pairs remain 0. Post-run counts are `decision_ledger=1`, `decision_outcome=0`, `ai_analysis_report=1`; schema fingerprint is unchanged. P2-03 remains `BLOCKED` with reason `INSUFFICIENT PROSPECTIVE OOS CALIBRATION HISTORY`.

Prospective provenance remediation (2026-10-02): root cause was that the TX futures builder did not attach standardized `sourceProvenance` to its analysis result. `record_ai_report()` already passed `analysis.sourceProvenance` into `record_decision()`; the field was absent upstream, so `source_metadata_json.source_provenance` became null. The futures builder now derives the existing P1-01 role structure from the provider results actually used (TAIFEX snapshot and Yahoo quote fields), preserves explicit normalized roles, and fails closed as `UNKNOWN` when source evidence is incomplete. API-to-Ledger and historical-immutability regressions pass using temporary databases. The old Decision fingerprint remains unchanged and its null provenance was not repaired or backfilled. The one authorized real runner re-verification completed Phase 1, then returned `DUPLICATE_MARKET_SESSION_SKIPPED` for the already captured `2026-10-01` session; counts and DB hash did not change. Therefore the code remediation is regression-verified, but real new-record provenance acceptance is `NOT VERIFIED` until a genuinely new market-session decision can be captured. P2-03 remains `BLOCKED`; no calibration sufficiency is established.

### P2-03 Historical As-Of Replay Calibration Research (2026-10-02)

Research track: `BLOCKED BEFORE REPLAY` (`EVIDENCE INSUFFICIENT`), classified as `HISTORICAL_RECONSTRUCTED_AS_OF_OOS`; this is not live prospective evidence. An isolated inventory retrieved 400 normalized TAIFEX TX daily observations spanning `2024-12-06` through `2026-10-01` (dataset SHA-256 `90b5f772a19e230d2212f66a1c522be0e95801f03fd8079d33235a16d3106930`). The current historical export has exchange trading dates and OHLC/change/volume/open-interest fields, but no per-row publication timestamps, archived vintages, or revision history. It also lacks historical decision-time provider-health, freshness, consistency, and fallback evidence; therefore the frozen `dataQualityScore` feature cannot be faithfully reconstructed. Strict PIT and complete-feature gates failed before replay. No reconstructed decisions, forecasts, targets, OOS pairs, or calibration metrics were generated. Artifacts are isolated under `.tmp/p203-historical-asof-replay/`; `data/p203-prospective-ledger.sqlite3` was not touched. `probabilityLabelAllowed=false`; the production/prospective P2-03 status remains `BLOCKED` for insufficient prospective OOS calibration history.

### P2-03 Historical Research Feature Contract V1 (2026-10-02)

Research feature contract V1: `IMPLEMENTED`. Isolated historical replay: `COMPLETE` under the frozen research-only contract. The separately authorized contract `P2_03_HISTORICAL_RESEARCH_FEATURES_V1` and model `P2_03_HISTORICAL_RESEARCH_LOGISTIC_V1` were frozen in `docs/P2_03_HISTORICAL_RESEARCH_FEATURE_CONTRACT_V1.md` before replay; frozen contract SHA-256 is `79eef16aec59844574b2dbde321a57f0982c844d25b334267eb48808d923f63d`. The isolated chronological replay used the same 400-session input (SHA-256 unchanged), generated 363 research-only OOS pairs (191 positive, 172 negative), and was deterministic across two runs. Model Brier was `0.2580047124`; the past-only expanding base-rate reference Brier was `0.2536138773`. Model ECE was `0.0678097176`; reference ECE was `0.0435423948`. No promotion threshold was authorized; interpretation is `EVIDENCE INCONCLUSIVE`. Source-vintage/publication-time availability remains unproven, and the main-contract series changes `contractMonth`; roll continuity is not independently verified. These pairs are `HISTORICAL_RESEARCH_AS_OF_OOS`, not production-contract, prospective, or live OOS evidence, and do not count toward prospective sample requirements. `data/p203-prospective-ledger.sqlite3` remained unchanged; `probabilityLabelAllowed=false`; production P2-03 remains `BLOCKED` for insufficient prospective OOS calibration history. Real new-record provenance remains `NOT YET VERIFIED`.

### P2-03 TX Contract-Roll Integrity Audit (2026-10-02)

Read-only roll audit: `COMPLETE`; conclusion `EXPOSURE PRESENT`. Revalidated the 400-session input SHA-256 `90b5f772a19e230d2212f66a1c522be0e95801f03fd8079d33235a16d3106930`, frozen V1 contract JSON SHA-256 `79eef16aec59844574b2dbde321a57f0982c844d25b334267eb48808d923f63d`, and all nine frozen V1 artifact hashes before and after analysis. The series contains 23 contract months and 22 transitions. Among 395 feature rows, `momentum_5` crosses contract months on 106 rows (26.84%), `open_interest_change_1` on 22 rows (5.57%), and either feature on 106 rows; `range_pct_1` has no direct cross-contract dependency, though 22 rows are roll-boundary sessions. Of 363 frozen OOS pairs, 249 are clean and 114 (31.40%) have potential feature, forecast-boundary, or target-return roll exposure; 20 targets cross contract months. All 363 reconstructed training sets matched the frozen trace's counts, classes, and target-date endpoints; every set contains at least one roll-affected feature and at least one roll-affected target label. Average combined affected training rows is 68.15, maximum 126. This is attribution only: V1 features, forecasts, labels, model, and calibration were not changed or rerun. Current `fetchers.py` selection code chooses the highest-volume contract per date when no month is specified, but the exact selector used to create the historical 400-row artifact is `NOT DETERMINABLE` because raw competing contract rows and an artifact-generation trace are absent. Audit outputs are under `.tmp/p203-contract-roll-audit/`; V1 artifact hashes and prospective DB hash/counts remained unchanged (`decision_ledger=1`, `decision_outcome=0`). Calibration remains `EVIDENCE INCONCLUSIVE`; `probabilityLabelAllowed=false`; P2-03 remains `BLOCKED` for insufficient prospective OOS calibration history.

### P2-03 Historical Research V1R1 Contract-Roll Clean Replay (2026-10-02)

Research-only V1R1: `DATASET PASS`; `SELECTION PROVENANCE PASS`; `ROLL-CLEAN INTEGRITY PASS`; `REPLAY PASS`. The frozen V1 contract/model/features/target/training minimum remain unchanged. TAIFEX returned 11,040 raw rows in 24 windows; 2,512 eligible TX contract candidates across 28 raw contract months produced 441 daily highest-volume selections spanning `2024-12-06` through `2026-10-01`. No maximum-volume ties occurred; selection used the checked-in parser, whose existing tie behavior is first eligible maximum-volume row. The old 400-session artifact is comparison-only: all 400 dates and their selected contract, close, volume, and open interest match; the raw rebuild adds 41 historical sessions missing from that artifact. There are 326 roll-clean feature rows and 303 clean matured labels; 31 candidates lack the required 30 clean matured training labels; 272 chronological forecasts/OOS pairs were generated. First forecast: `2025-03-05`, trained on 30 labels (12 positive, 18 negative). Valid-pair feature/target roll exposure and training feature/target roll exposure are all zero. V1R1 Brier/ECE are `0.2588409524` / `0.0595347228`; past-only baseline Brier/ECE are `0.2532434161` / `0.0300935998`. Interpretation remains `EVIDENCE INCONCLUSIVE`; no promotion threshold exists. Source vintage/publication timestamps and revision history remain `NOT PROVEN`. The 24 raw response files and V1R1 outputs are isolated under `.tmp/p203-historical-research-v1r1/`; per-window `retrievedAt` values were recovered from raw-file modification times after the initial output assembly stopped before writing its manifest. V1 artifacts and the prospective DB remain unchanged (`decision_ledger=1`, `decision_outcome=0`; DB SHA-256 `73db5d58f9cc1b2f5723ddbb86678036a6e5c67d322cf492d3b2d0f4d2f23df4`). V1R1 does not count toward prospective OOS minimums; `probabilityLabelAllowed=false`; production P2-03 remains `BLOCKED` for insufficient prospective OOS calibration history.

### P2-03 V1R1 Calibration / Coefficient Stability Diagnostic (2026-10-02)

Read-only research diagnostic: `COMPLETE`; root-cause evidence is available, while calibration remains `EVIDENCE INCONCLUSIVE`. The same 272 chronological V1R1 OOS pairs were used; frozen metric recomputation matched model/naive Brier `0.2588409524` / `0.2532434161` and ECE `0.0595347228` / `0.0300935998`. Brier Skill Score is `-0.02210338`; AUC is `0.48722548`; accuracy at 0.5 is `0.50`. Forecasts are concentrated in `[0.40,0.60)` (246/272, 90.44%), with 4 forecasts below 0.20 and 2 above 0.80. Mean forecast is `0.49901` against realized positive rate `0.53676`; per-bin calibration gaps have mixed directions, so systematic over/underconfidence is `NOT ESTABLISHED`. Calibration intercept/slope was `NOT CALCULATED` because the unpenalized calibration Hessian was singular. Model Brier is lower than naive in 3 of 7 fixed calendar quarters and higher in 4; model loss is better/worse/tied on 144/128/0 observations. Top 10 and top 20 observations contribute 8.71% and 13.54% of model Brier loss. Exact coefficient sign transitions were: intercept 11, momentum 19, range 3, and open-interest change 5; no substantive near-zero threshold was introduced. Quarterly feature distributions are reported descriptively; drift is not classified without a prespecified threshold. All diagnostics and regression tests are isolated under `.tmp/p203-v1r1-diagnostic/` and `regression/test_p203_v1r1_diagnostic_audit.py`. Two diagnostic runs produced identical output hashes; frozen V1R1 input fingerprints, contract SHA-256, and prospective DB SHA/counts remained unchanged. TAIFEX source vintage/publication timing and revision history remain `NOT PROVEN`; `probabilityLabelAllowed=false`; production P2-03 remains `BLOCKED` for insufficient prospective OOS calibration history. No model, calibration, feature, target, horizon, or production logic was changed.

### P2-03 Research V2 Pre-Registration (2026-10-02)

Owner adjudication: `FORMALLY APPROVED / FROZEN`; V2 implementation/execution remains `NOT AUTHORIZED / NOT STARTED`. Protocol: `docs/P2_03_RESEARCH_V2_PRE_REGISTRATION.md`; SHA-256 `0ab04d326962a48439f0a762f5967d0268d8137fae6e26e07db5c7ca39c55290` (verified unchanged). Manifest: `.tmp/p203-v2-protocol/protocol_manifest.json`; status `FORMALLY_APPROVED_FROZEN_NOT_EXECUTED`; manifest SHA-256 `9fbfd8cfe02bd47ace7893161bb6a5c1b6e9cba8639c6063c174cd91ef018ffb`; 38 V1R1 source hashes and 15 diagnostic hashes are unchanged. The approved contract/model IDs are `P2_03_HISTORICAL_RESEARCH_FEATURES_V2` / `P2_03_HISTORICAL_RESEARCH_LOGISTIC_V2`, with the frozen six-feature cap, V1 direction/target/horizon and logistic settings, highest-volume TX selection, and same-contract roll-clean rules. Historical development capacity is 441 selected sessions (2024-12-06–2026-10-01); exact V2 eligibility was not calculated. All existing historical sessions are already seen, so historical final evaluation is `NOT PRISTINE / NOT AVAILABLE`; independent final evaluation is `FUTURE PROSPECTIVE DATA ONLY`. The Owner-approved statistical gate is a 20-observation moving-block bootstrap, 10,000 iterations, fixed seed `2030301`, 95% intervals for model-minus-naive Brier difference and ROC AUC; it has not been run. Research signal support requires Brier-difference 95% CI upper bound `<0` and AUC 95% CI lower bound `>0.5`. Current prospective seed/final counts remain 0/0. Historical publication timing, vintages, and revision history remain `NOT PROVEN`; `probabilityLabelAllowed=false`; production P2-03 remains `BLOCKED` for insufficient prospective OOS calibration history. No V2 feature matrix, model, forecast, replay, bootstrap, or performance metric was generated.

### P2-03 Research V2 Protocol Amendment 001 (2026-10-02)

The original owner-approved V2 protocol remains frozen and unchanged: `docs/P2_03_RESEARCH_V2_PRE_REGISTRATION.md` (SHA-256 `0ab04d326962a48439f0a762f5967d0268d8137fae6e26e07db5c7ca39c55290`) and its original manifest (SHA-256 `9fbfd8cfe02bd47ace7893161bb6a5c1b6e9cba8639c6063c174cd91ef018ffb`). Amendment 001 documents the initialization semantic conflict and the Owner-adjudicated interpretation that the intercept uses V1 smoothed training-label log-odds initialization while feature weights initialize to zero. Amendment: `docs/P2_03_RESEARCH_V2_PROTOCOL_AMENDMENT_001.md`; effective identity: `.tmp/p203-v2-protocol/effective_protocol_identity.json`; versioned manifest: `.tmp/p203-v2-protocol/protocol_amendment_001_manifest.json`.

Amendment 001 was initially recorded as `CREATED — AWAITING OWNER APPROVAL`. On 2026-10-02, the Project Owner formally approved and froze it. Effective V2 Protocol: `ORIGINAL + AMENDMENT_001`, `FORMALLY APPROVED / FROZEN`. Effective initialization is V1-compatible smoothed prior-training-label log-odds for the intercept and zero initialization for feature weights. V2 Historical Development is `READY FOR SEPARATE OWNER AUTHORIZATION`; this approval does not authorize development. V2 implementation and final evaluation remain `NOT STARTED`. Production P2-03 remains `BLOCKED` for insufficient prospective OOS calibration history; `probabilityLabelAllowed=false`. Historical publication timing, vintages, and revision history remain `NOT PROVEN`. No V2 feature matrix, fit, forecast, replay, metric, bootstrap, or initialization comparison was performed.

### P2-03 Research V2 Historical Development (2026-10-02)

Historical development runner and regression were implemented under the separately authorized research-only scope. The frozen V1R1 inputs and source-selection trace were revalidated from 24 saved raw TAIFEX response windows; the 441-session selected series reconstructed identically under the highest-daily-volume TX rule. Two complete replay passes produced identical fingerprints. `P2-03 Research V2 Historical Development: BLOCKED` before model fit: 401 sessions are roll-ineligible under the frozen D−20 through D+1 same-contract rule, leaving only 19 matured eligible labels versus the required 30 prior labels. No forecast or OOS pair was generated; Brier, Brier Skill Score, AUC, and the development bootstrap are therefore unavailable. Bootstrap status is `NOT_RUN_NO_VALID_DEVELOPMENT_OOS_PAIRS`; the descriptive development gate is `NOT AVAILABLE`, not a pass/fail model result. Detailed isolated artifacts are under `.tmp/p203-v2-historical-development/` (manifest SHA-256 `81cdacb74d9da174f269d10284a95f792e3071e8a9188198cb073bc1ac710313`).

This historical window remains development-only, not pristine, independent, final, or prospective. Historical publication timing, vintages, and revision history remain `NOT PROVEN`. V2 Final Evaluation remains `NOT STARTED`; prospective seed/final counts remain 0/0; `probabilityLabelAllowed=false`; production P2-03 remains `BLOCKED` for insufficient prospective OOS calibration history. No V2 result supports a production claim.

## Later Nodes

| Node | Status | Execution |
|---|---|---|
| P1-04 | CLOSED | CLOSED |
| P2-01 | CLOSED | CLOSED |
| P2-02 | CLOSED | CLOSED |
| P2-03 | CLOSED | PASS — ENGINEERING / GOVERNANCE CLOSURE; statistical maturity pending; probabilityLabelAllowed=false |
| P2-04 | CLOSED | PASS — ENGINEERING / GOVERNANCE CLOSURE; realized performance evidence pending |
| P2-05 | CLOSED | PASS — ENGINEERING / GOVERNANCE CLOSURE; realized performance evidence unavailable |
| P3 | NOT AUTHORIZED | NOT STARTED |
| P4 | NOT AUTHORIZED | NOT STARTED |

### P2-05 Initial Contract Discovery (2026-10-02)

```text
INITIAL RESULT: BLOCKED — REGIME CONTRACT NOT DEFINED
STATUS: SUPERSEDED BY SUBSEQUENT OWNER AUTHORIZATION
```

At initial contract discovery, the repository had no authoritative frozen P2-05 regime definition, so execution correctly stopped before ledger access. A subsequent Project Owner authorization explicitly froze `P2_05_MARKET_SCORE_REGIME_V1`, authorized the narrow analyzer and regression, and permitted engineering closure on readiness despite pending realized evidence. The initial blocker is retained here as historical context; the current status is recorded below.

### P2-05 Formal Closure (2026-10-02)

```text
P2-05: CLOSED
RESULT: PASS — ENGINEERING / GOVERNANCE CLOSURE
REGIME CONTRACT: P2_05_MARKET_SCORE_REGIME_V1
REGIME CONTRACT SHA-256: e65588e9c771a06b6ee51bccefa0351033420824e77969092a875ac03edd11d2
REALIZED REGIME PERFORMANCE EVIDENCE: NOT AVAILABLE — NO ELIGIBLE EVALUATED OUTCOMES
POST-CLOSURE REGIME PERFORMANCE EVIDENCE: PENDING FUTURE AUTHORITATIVE OUTCOMES
FORMAL CLOSURE: APPROVED BY PROJECT OWNER AUTHORIZATION
P2-03: CLOSED
P2-04: CLOSED
P3: NOT AUTHORIZED / NOT STARTED
P4: NOT AUTHORIZED / NOT STARTED
```

The read-only authoritative ledger contained one Decision and zero Outcomes (SHA-256 `73db5d58f9cc1b2f5723ddbb86678036a6e5c67d322cf492d3b2d0f4d2f23df4`; latest `market_as_of` `2026-10-01`). The Decision's persisted `marketScore=50` mapped to `MID`; it was `NO_TRADE` with `decisionEligible=false`, so there were no eligible realized performance observations. The engineering and regression evidence is recorded in [P2_05_FORMAL_CLOSURE.md](P2_05_FORMAL_CLOSURE.md) (SHA-256 `ba731fa8381df5d0a1d4db89829b12187db08001103bb850fd002aa741a96109`).

## Governance and Promotion

```text
PROJECT OWNER = SOLE DECISION AUTHORITY

Proposal != Authorization
Draft != Execution
PASS != Formal Closure
Formal Closure != Git Promotion
Closed Node != Authorization for Next Node

NOT EXPLICITLY AUTHORIZED = PROHIBITED
UNCERTAIN = FAIL CLOSED
AUTHORIZED COMPLETE = HARD STOP
```

Current promotion authorization:

```text
Git Promotion: NOT AUTHORIZED
Commit: NOT AUTHORIZED
Push: NOT AUTHORIZED
PR: NOT AUTHORIZED
Merge: NOT AUTHORIZED
Deploy: NOT AUTHORIZED
```

Closing P1-01, P1-02, or P1-03 does not authorize P1-04 or any later node. Stop after completing an explicitly authorized node and wait for the Project Owner's next explicit decision.

### P2-04 — Score Bucket Performance (2026-10-02)

```text
Authorization: PROJECT OWNER AUTHORIZED; P2-03 SEQUENTIAL GATE WAIVED FOR P2-04 EXECUTION ORDER ONLY
P2-03: DEFERRED / BLOCKED; unchanged; probabilityLabelAllowed=false
Analyzer result at that execution: BLOCKED
Reason: NO ELIGIBLE EVALUATED OUTCOMES
P2-03 dependency: INDEPENDENT OF P2-03
```

The repository roadmap and the authorized data chain define score bucket performance from the immutable P2-01 Decision Ledger joined to P2-02 Outcome Evaluation. Calibrated probability is not an input. No P2-03 research artifact was used. The four score contracts are `marketScore`, `riskScore`, `evidenceScore`, and `dataQualityScore`; each has a documented/computed 0–100 decision-time range. `riskScore` is segmented by the P1-03 `riskClassification.type`; cross-instrument overall aggregation is suppressed unless frozen score formulas match, and cross-risk-type aggregation is suppressed. Fixed 10-point buckets are `[0,10)` through `[80,90)`, plus `[90,100]`; 100 is assigned to the final bucket. Any resulting rate is descriptive historical performance, not a probability forecast or calibration claim.

The authoritative non-production prospective ledger was inspected read-only using SQLite `mode=ro&immutable=1`. Its SHA-256 remains `73db5d58f9cc1b2f5723ddbb86678036a6e5c67d322cf492d3b2d0f4d2f23df4` (matching the known baseline); `decision_ledger=1`, `decision_outcome=0`. The single TX decision is `NO_TRADE` with `UNAVAILABLE` execution direction. Its immutable snapshot contains `marketScore=50`, `riskScore=51`, `evidenceScore=50`, and `dataQualityScore=75`. These fields are available for future bucket assignment, but there are no outcomes to evaluate. Therefore no performance table/CSV, success rate, or return statistic was generated. `NO_TRADE` is separately inventoried by score bucket and is not treated as a trade.

The P2-04 runner and isolated regression are `scripts/p204_score_bucket_performance.py` and `regression/test_p204_score_bucket_performance.py`. The runner produces only input inventory, score contract, eligibility funnel, integrity, determinism, and blocker summary artifacts under `.tmp/p204-score-bucket-performance/`. Two executions matched. Database, WAL, and SHM fingerprints were unchanged. The P2-04 regression (14 cases), P2-01 ledger, P2-02 outcome, and P1D ledger tests passed together (51 tests). No production rows, schema, score formulas, or P2-03 artifacts were modified.

At the time of this execution, the analyzer returned `BLOCKED — NO ELIGIBLE EVALUATED OUTCOMES`. Under the later Project Owner adjudication recorded below, this is retained as a realized-evidence maturity state rather than an engineering blocker. This descriptive node does not establish predictive validity, probability calibration, statistical significance, or production promotion.

### P2-04 Authorized Execution Re-verification (2026-10-02)

```text
P2-04: BLOCKED — NO ELIGIBLE EVALUATED OUTCOMES
Authoritative DB: data/p203-prospective-ledger.sqlite3 (read-only, immutable)
DB SHA-256: 73db5d58f9cc1b2f5723ddbb86678036a6e5c67d322cf492d3b2d0f4d2f23df4
Decision / Outcome rows: 1 / 0
Eligible EVALUATED LONG/SHORT outcomes: 0
probabilityLabelAllowed: false
P2-03: CLOSED (not consumed by P2-04)
P2-05 / P3 / P4: NOT AUTHORIZED / NOT STARTED
```

The refreshed immutable inventory found one TX decision (`NO_TRADE`, execution direction `UNAVAILABLE`, `decisionEligible=false`) and no Outcome rows. All canonical Outcome status counts are zero: `EVALUATED=0`, `PENDING=0`, `NOT_APPLICABLE=0`, `UNAVAILABLE=0`, `INVALID=0`. There are no joined Decision/Outcome IDs, orphan Outcomes, duplicate associations, or status/basis mismatches. The four frozen decision-time scores are valid and in range: `marketScore=50`, `riskScore=51`, `evidenceScore=50`, `dataQualityScore=75` (each 1 valid, 0 missing, 0 invalid, 0 out of range). No performance table, CSV, success rate, or return statistic was generated; the fixed ten-point bucket contract remains unchanged.

The authorized code review found that P2-04 previously admitted an `EVALUATED` LONG/SHORT join without requiring the persisted `decisionEligible` value to be the boolean `true`. The runner now records eligibility counts and excludes false, unknown, missing, and non-boolean values; a focused regression covers these cases. The summary also now reports the canonical `P2-03: CLOSED` state while retaining P2-04's independent P2-01 + P2-02 input chain. No P2-03 state, score formula, bucket boundary, database row, or schema was changed.

Final analysis was executed twice against the same authoritative input, with each invocation internally repeating the read-only build. Both output directories (`.tmp/p204-score-bucket-performance-authorized-20261002-final-run1/` and `...-final-run2/`) contain the same six non-performance artifacts with identical SHA-256 hashes. The in-run deterministic fingerprint is `b9a200a14294f38e62680ddd9e53e088a26f74b51052fb889ba7e3f029eb52ce`; `determinism_report.json` SHA-256 is `D4661C3FFECCAD30D2236C738441D59BA585D16EC72111CB0490D2BF485B3327`. The authoritative database and WAL/SHM sidecar fingerprints were unchanged.

Regression command (`MARKET_PULSE_DISABLE_BACKGROUND=1`): `python -B -m unittest regression.test_p204_score_bucket_performance regression.test_p2_01_decision_ledger regression.test_p2_02_outcome_evaluation regression.test_p2_03_probability_forecast regression.test_p1d_decision_outcome_ledger regression.test_p1_03_risk_classification` — 67 tests passed, including 15 P2-04 tests at that earlier execution. No eligible outcomes were available then. The later Owner-authorized closure below separates engineering readiness from pending realized-performance evidence and does not authorize P2-05 or any later node.

### P2-03 Prospective New-Session Capture / Source Provenance Verification (2026-10-02)

```text
P2-03: ACTIVE / BLOCKED
Provider-backed TAIFEX TX market date: 2026-10-01
Previously stored TX market date: 2026-10-01
Capture result: DUPLICATE_MARKET_SESSION_SKIPPED
New Decision: NOT INSERTED
Real new-record provenance: NOT VERIFIED — NO NEW PROVIDER SESSION
probabilityLabelAllowed: false
```

The TAIFEX official futures daily OpenAPI returned a parsed TX snapshot with market date `2026-10-01` (contract month `202610`, source URL `https://openapi.taifex.com.tw/v1/DailyMarketReportFut`). A read-only preflight observed it at `2026-10-02T08:59:49.145220+00:00`; the provider response did not supply a distinct `source_updated_at`, so retrieval time was not substituted for that field. The one-shot `scripts/p203_prospective_evidence_runner.py` then preserved its required order: checked due outcomes first, followed by the current provider date and duplicate-session guard. It returned `DUPLICATE_MARKET_SESSION_SKIPPED` for existing decision `cd5434d8bf864e83a9eaf22382b859ee0d89a6da247d837ef968825935ff7267`; the analysis API was not invoked.

Phase 1 checked 1 existing decision, evaluated 0, left 0 pending, skipped 1, and produced 0 valid OOS pairs. Counts after the run: LONG `0`, SHORT `0`, NO_TRADE `1`, HOLD_EXISTING `0`, UNKNOWN `0`; `decisionEligible=true` `0`, `false` `1`; all outcome statuses `0`. No Outcome or Decision row was inserted. Before/after DB SHA-256 stayed `73db5d58f9cc1b2f5723ddbb86678036a6e5c67d322cf492d3b2d0f4d2f23df4`; counts stayed `decision_ledger=1`, `decision_outcome=0`, `ai_analysis_report=1`, and schema fingerprint was unchanged. The complete existing Decision rows fingerprint stayed `d6c863a9a1e208178db81bc3e307b5743ae87691fcf8ea94aaed44daef7195df`; updated existing rows `0`, deleted existing rows `0`. The old TX record remains `NO_TRADE`, `decisionEligible=false`, source provenance `null`, with `source_updated_at=2026-10-01`, `probabilityForecast=null`, `probabilityForecastStatus=UNAVAILABLE_INELIGIBLE_DECISION`, and `probabilityLabelAllowed=false`.

Prospective evidence after the run: eligible matured training labels `0` (positive `0`, negative `0`); persisted prospective forecasts `0`; valid prospective OOS pairs `0`. The old decision's absent source provenance remains unchanged and was not backfilled. Because no new provider session produced a new record, the real new-record provenance gate is `NOT VERIFIED — NO NEW PROVIDER SESSION`. Historical V2 remains separately blocked at 19 eligible labels versus 30 required. P2-04 remains `BLOCKED — NO ELIGIBLE EVALUATED OUTCOMES`; it was not rerun.

Live-path regressions (separate from provider evidence):

```text
$env:MARKET_PULSE_DISABLE_BACKGROUND = '1'
python -B -m unittest regression.test_p203_prospective_evidence_runner regression.test_p203_source_provenance regression.test_p2_02_outcome_evaluation regression.test_p2_03_probability_forecast
31 tests PASS
```

The live one-shot command was `python -B scripts/p203_prospective_evidence_runner.py` (the runner itself disables background activity and fixes `DERIVATIVES_DB_PATH` to the canonical local evidence database).

No source code or tests were changed for this run. This result does not close P2-03 or authorize later nodes.

### P2-03 TAIFEX UTF-8 BOM Parsing Remediation (2026-10-02)

```text
TAIFEX UTF-8 BOM parsing remediation: PASS
P2-03: ACTIVE / BLOCKED
Live provider verification: NOT EXECUTED
Prospective capture: NOT EXECUTED
probabilityLabelAllowed: false
```

The prior read-only TAIFEX fetch failed at `fetch_registry.py` JSON response decoding with `JSONDecodeError: Unexpected UTF-8 BOM`, confirming a leading BOM reached the JSON parser. The response body was not retained, so its full live payload was not independently revalidated. The shared JSON decoder now decodes with `utf-8-sig`, which accepts one leading UTF-8 BOM while preserving normal UTF-8 behavior and internal U+FEFF string content. Regression coverage includes plain JSON from a non-TAIFEX source, a TAIFEX-shaped TX row with market-date extraction, malformed and empty JSON, HTML, invalid bytes, non-leading/double BOM, and internal U+FEFF preservation.

Verification command: `python -B -m unittest regression.test_fetch_registry_bom regression.test_p0a_market_time_integrity regression.test_p203_source_provenance regression.test_p203_prospective_evidence_runner` — 24 tests passed. The prospective runner tests use temporary isolated databases. No live provider request, authoritative database access, live market-date gate, Decision capture, or Outcome evaluation was performed for this remediation. Live market-date verification remains pending separate Project Owner authorization; real new-record provenance remains `NOT VERIFIED`.

### P2-03 Live Market-Date Gate after BOM Remediation (2026-10-02)

```text
TAIFEX BOM remediation live check: FAIL — live fetch remained unparseable
Provider market_date: UNKNOWN
Live market-date gate: NOT ESTABLISHED
Prospective capture: NOT EXECUTED
Real new-record provenance: NOT VERIFIED — NO CAPTURE
P2-03: ACTIVE / BLOCKED
probabilityLabelAllowed: false
```

One project-fetcher request to the TAIFEX TX daily futures OpenAPI started at `2026-10-02T11:02:07.313334+00:00` and returned from the fetch path at `2026-10-02T11:02:07.870430+00:00` with `JSONDecodeError: Expecting value: line 1 column 1 (char 0)`. No market date, `market_as_of`, or `source_updated_at` was obtained. The response status/body were not retained, so this does not establish whether the response was empty, whitespace, or another non-JSON payload; the single authorized request was not retried. The earlier BOM-specific parser regression remains 5/5 PASS, but this live request did not pass.

The market-date capture gate was not established, so the runner was not called. Read-only ledger snapshots before and after the fetch match: SHA-256 `73db5d58f9cc1b2f5723ddbb86678036a6e5c67d322cf492d3b2d0f4d2f23df4`, `decision_ledger=1`, `decision_outcome=0`, latest market date `2026-10-01`, and existing Decision ID `cd5434d8bf864e83a9eaf22382b859ee0d89a6da247d837ef968825935ff7267`. The existing row fingerprint remains `59de9a733b309a3b6d14bc4a009eca1bcfee7960c8d6e5086f2dd5b920c51420`; it remains `NO_TRADE`, ineligible, with null probability forecast and source provenance. No Decision or Outcome was inserted. P2-04 remains `BLOCKED — NO ELIGIBLE EVALUATED OUTCOMES`; no later node was run.

### P2-03 TAIFEX Live Response Recovery / Market-Date Gate (2026-10-02)

```text
Initial response: HTTP 200; INVALID_JSON; BOM-prefixed CSV-like TAIFEX header observed
Single remediation: IMPLEMENTED; allow JSON or recognized TAIFEX CSV at the TX daily fetch boundary
Focused regressions: 26 PASS
Post-remediation response: HTTP 200; INVALID_JSON; production parser rejected unrecognized CSV header
TAIFEX live response recovery: BLOCKED
Provider market_date: UNKNOWN
Market-date gate: NOT ESTABLISHED
Prospective capture: NOT EXECUTED
Real new-record provenance: NOT VERIFIED — NO CAPTURE
P2-03: ACTIVE / BLOCKED
probabilityLabelAllowed: false
```

The initial read-only transport diagnostic at `2026-10-02T11:23:41.125754Z`–`11:23:41.744674Z` used the production TAIFEX endpoint and project SSL transport. It returned HTTP 200 from the original URL without redirect; `Content-Type=application/octet-stream`, `Content-Length=167219`, no `Content-Encoding`, actual body length 167219 bytes, one leading UTF-8 BOM, nonempty/non-whitespace body, and no HTML signature. `utf-8-sig` decoding succeeded, but JSON parsing failed with `JSONDecodeError: Expecting value: line 1 column 1 (char 0)`. The bounded preview showed a Chinese comma-delimited market header, so this was a JSON-versus-CSV format mismatch rather than the earlier BOM failure.

Within the single authorized remediation cycle, `fetchers.py` changed the TAIFEX daily endpoint to retain its existing JSON row support and accept only CSV with recognized TAIFEX headers; `regression/test_fetch_registry_bom.py` added a sanitized CSV fixture and fail-closed cases. Focused command `python -B -m unittest regression.test_fetch_registry_bom regression.test_p0a_market_time_integrity regression.test_p203_source_provenance regression.test_p203_prospective_evidence_runner` passed 26 tests.

The one post-remediation request at `2026-10-02T11:26:32.526504Z`–`11:26:33.058985Z` again returned HTTP 200 from the same URL with `application/octet-stream`, `Content-Length=167219`, no redirect, and 167219 bytes. The body remained BOM-prefixed and non-JSON; the production TAIFEX parser rejected its CSV header as unrecognized, so no TX market date or `market_as_of` was extracted. `source_updated_at` was not supplied. No further request or remediation cycle was attempted under this authorization.

Read-only ledger checks before/after this task matched: SHA-256 `73db5d58f9cc1b2f5723ddbb86678036a6e5c67d322cf492d3b2d0f4d2f23df4`; one Decision, zero Outcomes; latest date `2026-10-01`; original Decision ID `cd5434d8bf864e83a9eaf22382b859ee0d89a6da247d837ef968825935ff7267`; row fingerprint `59de9a733b309a3b6d14bc4a009eca1bcfee7960c8d6e5086f2dd5b920c51420`. Existing rows updated/deleted: `0`/`0`. No runner ran, no prospective counts were recalculated, and no new authoritative Outcome exists for P2-04. The remaining P2-03 blocker is that the observed live CSV header is not parsed by the one-cycle implementation; live date verification and new-record provenance remain unverified.

### P2-03 TAIFEX Live CSV Header Recovery / Market-Date Gate (2026-10-02)

```text
TAIFEX live CSV recovery: PASS
Initial response: TAIFEX_CSV_UNRECOGNIZED_HEADER
Post-remediation response: TAIFEX_CSV_VALID
Provider market_date: 2026-10-01
Stored latest market_date: 2026-10-01
Market-date gate: NOT ADVANCED
Prospective capture: NOT EXECUTED
New-record provenance: NOT VERIFIED — NO NEW DECISION
P2-03: ACTIVE / BLOCKED
probabilityLabelAllowed: false
```

Initial live header evidence is retained at `.tmp/p203-taifex-live-csv/live_header_evidence.json`; post-remediation evidence is at `.tmp/p203-taifex-live-csv/post_remediation_evidence.json`. The initial response was HTTP 200, `application/octet-stream`, 167219 bytes, with one leading UTF-8 BOM and no redirect. The complete 19-column header SHA-256 is `a7bdb581e0a8c907c38342409e9c5fc717e8dd2cb9941c1f499896deebb00814`; the first data row had 19 fields, matching the header. The verified header was `日期,契約代號,到期月份(週別),開盤價,最高價,最低價,最後成交價,漲跌價,漲跌%,合計成交量,結算價,未沖銷契約數,最後最佳買價,最後最佳賣價,歷史最高價,歷史最低價,是否因訊息面暫停交易,交易時段,價差對單式委託成交量`.

The existing parser used header-name mapping, accepted `契約`/`商品` for Contract and `漲跌價差`/`漲跌` for Change, required Date, Contract, and Last or SettlementPrice, and treated OHLC fallbacks as before. The live labels `契約代號` and `漲跌價` were missing aliases; the six bid/ask, historical, pause-status, and spread-volume columns are optional extras. Root cause classification: `HEADER_ALIAS_CHANGE`, `REQUIRED_COLUMN_RENAME`, and `ADDED_OPTIONAL_COLUMNS`; no semantic change or column-position assumption was introduced.

The narrow TAIFEX parser now maps the two observed aliases by header name, requires consistent row widths, rejects duplicate/unknown or missing required headers, and ignores extra columns only when the row width matches. Existing JSON support, BOM semantics, numeric conversion, row selection, and date normalization remain unchanged. The sanitized regression uses the observed 19-column header and synthetic values; it covers TX date/month/numeric extraction, reordered columns, an extra optional column, unknown and missing required headers, malformed row width, and the existing JSON/BOM failures. Focused command `python -B -m unittest regression.test_fetch_registry_bom regression.test_p0a_market_time_integrity regression.test_p203_source_provenance regression.test_p203_prospective_evidence_runner` passed 30 tests.

The one post-remediation request at `2026-10-02T11:38:37.648927Z`–`11:38:38.256762Z` returned HTTP 200 from the same endpoint, no redirect, `application/octet-stream`, 167219 bytes, with a leading BOM. Header SHA-256 matched the initial response. The production parser read 2192 rows, including 16 TX rows; the existing selector chose TX contract month `202610` with market date `2026-10-01`, close `48685.0`, settlement `48698.0`, volume `34458.0`, and open interest `107607.0`. `market_as_of=2026-10-01` is the normalized value of the provider `日期` field; no separate `source_updated_at` was supplied. The first-row bounded hex preview is retained in the artifact.


### P2-03 Historical Roll-Continuity Feasibility + Prospective Readiness Audit (2026-10-02)

```text
Audit: COMPLETE — READ-ONLY / RESEARCH DIAGNOSTIC
Frozen V2 replay: REPRODUCED; 19 matured labels < 30 required prior labels
Frozen-rule forecasts / OOS pairs: 0 / 0
Isolated prospective regression: 45 PASS
Authoritative prospective DB: UNCHANGED
P2-03: ACTIVE / BLOCKED; probabilityLabelAllowed=false
P2-04: BLOCKED — NO ELIGIBLE EVALUATED OUTCOMES; not run
```

The deterministic audit script `scripts/p203_roll_continuity_feasibility_audit.py` reloaded the 24 saved raw TAIFEX windows, reconstructed the selected 441-session TX series, and verified the selected-series SHA-256 `90ca05e0472b09ba3f67e641dae16f8ed9ad310fc87d056e7fd2c3e0baa1c48f` and selection-trace SHA-256 `a1f5bfd250f1cb94f09a7324f5314686fc29e298cde649a26dd4f817e11e251a`. Frozen protocol, Amendment 001, and effective identity hashes matched `0ab04d326962a48439f0a762f5967d0268d8137fae6e26e07db5c7ca39c55290`, `80ae6beafeeebc68776249625162d6a18736cd1c91981708b71c9dbda852ae0a`, and `f229f03eb3d931aae96d1e994cb8725f8a73676132632da28c94cc9e4d8fcafc`. Two independent audit-output directories had identical artifact manifests.

The exact frozen funnel was reproduced: 441 selected sessions; 20 warmup exclusions; 401 roll-ineligible sessions (395 feature-window, 21 target-boundary, with 15 overlapping); 1 unavailable target; no incomplete features, direction exclusions, or flat targets; 19 matured labels; 19 candidates below the 30-prior-label minimum; no forecast and no OOS pair. Roll exclusions partition into 380 feature-only, 6 target-only, and 15 overlapping sessions. The selected series has 23 contract runs and 22 transitions; run lengths are 9–25 sessions (median 19, mean 19.173913), with 11 runs of at least 20 sessions, 6 of at least 21, and 6 of at least 22. Under the frozen rules, the fixed window's maximum forecast and OOS capacity is zero. The protocol's same-contract feature/target continuity is a frozen research-design condition; strictly prior decision and matured-target chronology are anti-leakage requirements. Historical provider publication timing, vintage, and revision history remain `NOT PROVEN`.

Counterfactual diagnostics only (not approved, implemented, or evidence for changing the frozen protocol) yielded 294 labels with a 5-session feature-continuity window, 190 with 10, 86 with 15, 19 with 20, and 399 when only the target session is required to remain in-contract. Ignoring contract switching entirely yielded 420. The larger counts show that feature-window continuity is the main numerical constraint in this selected active-contract history; they do not establish these alternatives as leakage-safe or acceptable. No OOS metric was calculated.

Verification command: `python -B -m unittest regression.test_p203_prospective_evidence_runner regression.test_p203_source_provenance regression.test_p2_02_outcome_evaluation regression.test_p2_03_probability_forecast regression.test_p203_v2_historical_development` — 45 tests passed. An additional isolated synthetic boundary check confirmed sample counts 0–29 all return `INSUFFICIENT_TRAINING_HISTORY`, 30 balanced labels return a probability forecast, and 30 single-class labels fail closed as `INSUFFICIENT_TARGET_VARIATION`. The existing tests also cover T+1 target semantics, LONG/SHORT eligibility, NO_TRADE/HOLD exclusions, chronology and future-row exclusion, prospective provenance, duplicate-session guard, API/Ledger round trip, preservation of older rows, and `probabilityLabelAllowed=false`. Scores are model inputs; a 68 market score in the synthetic check produced probability `0.746169790163`, not `0.68`.

Only isolated test databases were written. Read-only immutable snapshots of `data/p203-prospective-ledger.sqlite3` before and after testing matched SHA-256 `73db5d58f9cc1b2f5723ddbb86678036a6e5c67d322cf492d3b2d0f4d2f23df4`, with one Decision and zero Outcomes. The audit artifacts are under `.tmp/p203-roll-continuity-feasibility-audit/` and a repeat run under `.tmp/p203-roll-continuity-feasibility-audit-repeat/`; neither contains authoritative prospective records. No live provider request, capture, P2-04 execution, model/protocol change, or node transition occurred. The readiness results validate isolated pipeline behavior only; real new-session provenance and prospective OOS sufficiency remain unverified/insufficient, so P2-03 remains ACTIVE / BLOCKED.

### P2-03 Formal Closure — Amendment 002 (2026-10-02)

```text
P2-03: CLOSED
RESULT: PASS — ENGINEERING / GOVERNANCE CLOSURE
Historical V2: RESEARCH_ONLY / COMPLETE AS RESEARCH DIAGNOSTIC
Prospective Pipeline: ENGINEERING READY
Prospective Statistical Maturity: PENDING FUTURE REAL OBSERVATIONS
Eligible matured labels: 0 currently
Forecast gate: >=30 eligible matured labels AND both classes
probabilityLabelAllowed: false
```

The Project Owner formally approved `docs/P2_03_PROTOCOL_AMENDMENT_002.md` (SHA-256 `3b3d2b37aef0a0480ec6c0ac6aab8387c0b4ed4c53b8f9f8801025c41002f376`). Its effective identity is Original V2 + Amendment 001 + Amendment 002, SHA-256 `8783fb841427ee1fba44ac93d3f2e1186850b179fd4042777664f0c211e174f3`; the prior Original + Amendment 001 identity `f229f03eb3d931aae96d1e994cb8725f8a73676132632da28c94cc9e4d8fcafc` remains preserved. Frozen historical V2 is classified `HISTORICALLY INFEASIBLE UNDER CURRENT CONTRACT` for its 441-session development dataset (19 labels, 0 forecasts, 0 OOS) and is removed from P2-03 closure gating. Its inputs and results remain unchanged. Prospective production contracts and all chronology, outcome, provenance, sample-size, both-class, and fail-closed protections remain in force.

The final scoped regression passed 67 tests, including Amendment 002 and roll-continuity assertions. The authoritative prospective database remained unchanged at SHA-256 `73db5d58f9cc1b2f5723ddbb86678036a6e5c67d322cf492d3b2d0f4d2f23df4`, with one Decision and zero Outcomes. The deterministic closure manifest is under `.tmp/p203-formal-closure-final/`; the repeated generation under `.tmp/p203-formal-closure-final-repeat/` matches. Synthetic evidence is test-only. This closure establishes no predictive validity, calibration, profitability, trading edge, or probability-label approval.

```text
P2-04: BLOCKED — NO ELIGIBLE EVALUATED OUTCOMES (not run in this closure)
P2-05: NOT AUTHORIZED / NOT STARTED
P3: NOT AUTHORIZED / NOT STARTED
P4: NOT AUTHORIZED / NOT STARTED
```

P2-03 formal closure does not authorize P2-04 execution, any later node, Git promotion, live capture, or deployment. Prospective evidence accumulation continues only under its existing separately authorized operational mechanism.

## P2-04 Formal Closure — Engineering / Governance (2026-10-02)

```text
P2-04: CLOSED
RESULT: PASS — ENGINEERING / GOVERNANCE CLOSURE
ENGINEERING / ANALYTICS READINESS: PASS
REALIZED PERFORMANCE EVIDENCE: NOT AVAILABLE — NO ELIGIBLE EVALUATED OUTCOMES
POST-CLOSURE PERFORMANCE EVIDENCE: PENDING FUTURE AUTHORITATIVE OUTCOMES
P2-03: CLOSED
P2-05: NOT AUTHORIZED / NOT STARTED
P3: NOT AUTHORIZED / NOT STARTED
P4: NOT AUTHORIZED / NOT STARTED
```

Project Owner authorized closing P2-04 based on deterministic, read-only, fail-closed engineering readiness. The current authoritative ledger contains one `NO_TRADE` decision with `decisionEligible=false` and zero Outcomes, so no realized performance table or statistics exist. This closure does not assert predictive validity, statistical significance, profitability, or trading edge. The closure evidence is recorded in `docs/P2_04_FORMAL_CLOSURE.md`; future authoritative outcomes may use the completed analyzer as post-closure operational evidence accumulation without reopening P2-04 engineering.

## Phase 3 — Model Validation Strengthening (2026-10-02)

```text
P3-00 Current-State / Contract / Executability Audit: PASS (Owner-adjudicated)
Phase 3: ACTIVE
P3-01 Walk-Forward Validation: CLOSED (Owner-adjudicated); Engineering PASS; Pipeline READY
P3-01 Statistical Evidence: NOT YET MATURE
P3-02 Regime-Conditioned Validation: CLOSED (Owner-adjudicated); Engineering PASS; Validation Pipeline READY
P3-02 Statistical Evidence: NOT YET MATURE; authoritative realized regime statistics NOT AVAILABLE
P3-03 Net Expectancy Validation: CLOSED; Result PASS — ENGINEERING / GOVERNANCE CLOSURE; Engineering PASS; Validation Pipeline READY
P3-04 Model Drift / Temporal Stability: CLOSED; Result PASS — ENGINEERING / GOVERNANCE CLOSURE; Engineering PASS; Temporal-Stability Pipeline READY; Authoritative Drift Evidence NOT AVAILABLE — INSUFFICIENT TEMPORAL OBSERVATIONS; Drift Presence NOT ESTABLISHED; Drift Absence NOT ESTABLISHED; Model Retraining Need NOT ESTABLISHED; Formal Acceptance APPROVED BY PROJECT OWNER
Phase 3 Formal Closure: NOT STARTED
P4: NOT AUTHORIZED / NOT STARTED
Git Promotion: NOT AUTHORIZED
```

The minimum Phase 3 contract is frozen in `docs/PHASE3_MODEL_VALIDATION_CONTRACT.md`, Contract ID `PHASE3_MODEL_VALIDATION_V1`, SHA-256 `43ebcad66cd8267c07bca2419fbbcdeca066e6195eecf1e4ac782fd5954bbc57`. It fixes the sequence as P3-01 Walk-Forward → P3-02 Regime-Conditioned → P3-03 Net Expectancy → P3-04 Model Drift / Temporal Stability. P3-01 and P3-02 were subsequently closed by Project Owner adjudication; P3-03 execution is recorded below.

P3-01 evaluates the unchanged P2-03 baseline: target `P2_03_DIRECTIONAL_SUCCESS_V1`, T+1 observed market session, features `P2_03_DERIVATIVES_SCORE_FEATURES_V1`, and deterministic standard-library logistic regression `P2_03_LOGISTIC_REGRESSION_V1`. The fold is one eligible Decision per holdout with an expanding same-instrument training set. Training labels must be P2-02 `EVALUATED` labels whose decision and evaluation times strictly precede the held-out decision. The existing 30-label / both-class training gate, immutable Decision and separate Outcome contracts, point-in-time inputs, prospective forecast identity, and `probabilityLabelAllowed=false` are retained. No extra calendar embargo, transaction-cost change, target/feature/horizon/window change, regime-boundary change, or production-model change was made. Each persisted forecast is recomputed with the existing fitter; its own Outcome is considered only after the forecast is verified. Synthetic fixtures are classified test-only and cannot contribute to authoritative evidence counts.

The read-only authoritative ledger `data/p203-prospective-ledger.sqlite3` was inspected before and after P3-01. Database SHA-256 remained `73db5d58f9cc1b2f5723ddbb86678036a6e5c67d322cf492d3b2d0f4d2f23df4`; `PRAGMA integrity_check` returned `ok`; schema SHA-256 remained `ca582e7521891078d88713c794a0b998c973972b71bd92df64e8b64ef8296c52`; counts remained one Decision and zero Outcomes. The sole TX Decision is `NO_TRADE`, `UNAVAILABLE`, and ineligible. There are 0 eligible candidate Decisions, 0 eligible matured labels, 0 persisted probability forecasts, 0 valid prospective walk-forward pairs, and no observed target class. Consequently, no fold was available for empirical replay, Brier score is `null`, calibration status is `INSUFFICIENT_SAMPLE`, and statistical evidence remains `NOT YET MATURE` (<30 eligible prospective OOS pairs and no two-class OOS sample). The pipeline-ready result is not a statistical validation result.

Two separate CLI processes (`python -B -m derivatives.walk_forward_validation`) produced the same report fingerprint `9278c1688a49ed27c95bcf2219d9d2285ebc104a7eedb46025ccc974fc54463f`; both confirmed the database unchanged. Chronology and leakage safeguards are implemented and covered by isolated synthetic regression, but actual forecast/outcome chronology was `NOT OBSERVED` because there are no eligible OOS pairs. The P3-01 regression command `$env:MARKET_PULSE_DISABLE_BACKGROUND='1'; python -B -m unittest regression.test_p2_03_probability_forecast regression.test_p2_02_outcome_evaluation regression.test_p2_01_decision_ledger regression.test_p301_walk_forward_validation` passed 31 tests. Python AST syntax checks passed for the new module and test; `git diff --check` passed. No authoritative DB write, live provider request, model/decision/outcome mutation, metric-driven tuning, probability-label promotion, P3-02 execution, Git promotion, or deployment occurred.

This work establishes deterministic walk-forward pipeline readiness only. It does not establish predictive validity, calibrated probability, positive Brier skill, AUC above chance, statistical significance, profitability, net expectancy, regime-specific performance, temporal stability, production promotion, or `probabilityLabelAllowed=true`. P3 remains active pending mature prospective evidence and separately authorized later nodes.

## P3-02 Regime-Conditioned Validation — Engineering Execution (2026-10-02)

```text
P3-01: CLOSED (Project Owner adjudication)
P3-02 Status: ACTIVE — EXECUTION COMPLETE; FORMAL ACCEPTANCE PENDING
P3-02 Engineering: PASS
P3-02 Validation Pipeline: READY
P3-02 Statistical Evidence: NOT YET MATURE
P3-02 Authoritative Realized Regime Statistics: NOT AVAILABLE
P3-03 / P3-04: NOT AUTHORIZED / NOT STARTED
P4: NOT AUTHORIZED / NOT STARTED
```

The P3-02 contract is frozen at `docs/P3_02_REGIME_CONDITIONED_VALIDATION_CONTRACT.md`, SHA-256 `ee105670157843b9f90afc0467b17d2a5b9c19551e4e475c5f693ff055d06629`. It reuses P2-05 contract `P2_05_MARKET_SCORE_REGIME_V1` (SHA-256 `e65588e9c771a06b6ee51bccefa0351033420824e77969092a875ac03edd11d2`) and P3-01's frozen walk-forward checks. Regime assignment reads only the persisted decision-time `marketScore`; LOW `[0,40)`, MID `[40,60)`, HIGH `[60,100]`. Invalid or missing scores fail closed. The unchanged global P2-03 model and P3-01 chronology are retained; no regime-specific fit, target, feature, horizon, threshold, cost, or boundary change was made.

The read-only authoritative database was unchanged across P3-02: SHA-256 `73db5d58f9cc1b2f5723ddbb86678036a6e5c67d322cf492d3b2d0f4d2f23df4`; one Decision; zero Outcomes; schema fingerprint `ca582e7521891078d88713c794a0b998c973972b71bd92df64e8b64ef8296c52`; `PRAGMA integrity_check=ok`; eligible directional Outcomes `0`. Decision coverage is LOW `0`, MID `1`, HIGH `0`; the sole MID Decision is `NO_TRADE` / ineligible. Eligible T+1 directional Outcomes, non-flat target observations, replay-verified forecasts, and valid OOS pairs are all `0`. Therefore Brier, mean forecast, realized positive rate, and decision-aligned return are `null`; Brier Skill and net return are not calculated; `probabilityLabelAllowed=false`.

Two independent authoritative CLI report generations had identical fingerprint `79c8b027dfae4dbd454a643122f29b4b30fd660d26bacb1b3451f42daea52912`. The focused command `$env:MARKET_PULSE_DISABLE_BACKGROUND='1'; python -B -m unittest regression.test_p2_03_probability_forecast regression.test_p203_prospective_evidence_runner regression.test_p203_source_provenance regression.test_p2_02_outcome_evaluation regression.test_p2_01_decision_ledger regression.test_p204_score_bucket_performance regression.test_p205_regime_performance regression.test_p301_walk_forward_validation regression.test_p302_regime_conditioned_validation` passed 85 tests. P3-02 synthetic fixtures exercise only boundaries, partition isolation, chronology, eligibility filtering, `NO_TRADE` exclusion, fail-closed scores, and determinism; their 30 test-only OOS pairs are excluded from authoritative counts.

Pipeline readiness does not establish regime predictive validity, statistical significance, regime monotonicity, profitability, alpha, trading edge, calibration success, or probability-label promotion. No eligible authoritative regime evidence matured. At the time of this execution, it did not itself close the node or authorize P3-03; Project Owner subsequently closed P3-02 and authorized continuation within Phase 3.

## P3-03 Net Expectancy Validation — Execution and Producer Compatibility Repair (2026-10-03)

```text
P3-01: CLOSED (Project Owner adjudication)
P3-02: CLOSED (Project Owner adjudication)
P3-03: CLOSED
P3-03 Result: PASS — ENGINEERING / GOVERNANCE CLOSURE
P3-03 Engineering: PASS
P3-03 Validation Pipeline: VALIDATION PIPELINE READY
P3-03 Authoritative Outcomes: 0
P3-03 Cost-Qualified Expectancy Observations: 0
P3-03 Realized Net Expectancy: NOT AVAILABLE
P3-03 Statistical Maturity: NOT YET MATURE — NO FROZEN P3-03 SUFFICIENCY GATE
P3-04: NOT STARTED — no detailed frozen P3-04 execution contract found
P4: NOT AUTHORIZED / NOT STARTED
```

The Phase 3 contract remains `PHASE3_MODEL_VALIDATION_V1`, SHA-256 `43ebcad66cd8267c07bca2419fbbcdeca066e6195eecf1e4ac782fd5954bbc57`. The P3-03 contract remains `P3_03_NET_EXPECTANCY_VALIDATION_V1`, SHA-256 `056a9216e693e6e2cf2c403c988b4624c81ed4cf7110314e1c8c8e7f3e6ba058`; neither frozen contract was changed.

The direct P2-02 producer defect was that a versioned Outcome carried `outcomeStatus=EVALUATED` in metadata but persisted evaluator availability (`AVAILABLE` / `PARTIAL`) in the authoritative `status` column. P2-04 requires the column itself to be canonical `EVALUATED` and does not upgrade legacy values. The minimal repair persists the versioned canonical status, preserves evaluator status in `legacyStatus` metadata and preserves `data_quality_status`; unversioned `AVAILABLE` / `PARTIAL` remains unpromoted. Conflicting versioned statuses are rejected. No schema, decision, return, cost, score, or strategy calculation changed. Ledger API `legacyStatus` remains backward-compatible.

Focused dependency regressions passed: 114 tests across P1D Outcome Ledger, P2-01, P2-02, P2-03, P2-04, P2-05, P3-01, P3-02, and P3-03. Python in-memory syntax checks passed for the four modified Python files. `git diff --check` passed. Two independent authoritative P3-03 CLI processes produced the same report fingerprint `11e562780c728b9fd6fad1bf111e20b42c255208a17af072c9848f7b096df785`.

The read-only authoritative ledger `data/p203-prospective-ledger.sqlite3` remained unchanged: SHA-256 `73db5d58f9cc1b2f5723ddbb86678036a6e5c67d322cf492d3b2d0f4d2f23df4`; schema SHA-256 `ca582e7521891078d88713c794a0b998c973972b71bd92df64e8b64ef8296c52`; SQLite application ID `1345466419`; `PRAGMA integrity_check=ok`; one Decision, zero Outcomes, zero eligible evaluated directional T+1 Outcomes, and zero cost-qualified expectancy observations. WAL/SHM fingerprints were unchanged. The existing Decision remains ineligible; P3-01 observed zero prospective forecasts and zero OOS pairs; `probabilityLabelAllowed=false` remains in force.

No authoritative expectancy metric was produced: Net Expectancy and related sample metrics remain `null` / `NOT AVAILABLE`, not zero. No claim is made about profitability, alpha, trading edge, statistical significance, predictive validity, calibration, or probability-label promotion. No authoritative DB write, probability promotion, model change, Git promotion, or deployment occurred. Project Owner formally accepted and closed P3-03 on 2026-10-03. P3-04 remains unexecuted, and Phase 3 remains active without formal closure.

## P4-01 Builders / Fetchers Domain — Formal Closure (2026-10-03)

```text
P4-01: CLOSED
RESULT: PASS — ENGINEERING / GOVERNANCE CLOSURE
ENGINEERING: PASS
BUILDERS / FETCHERS DOMAIN: VERIFIED
DIRECT BUILDER TRANSPORT OWNERSHIP: REMOVED
KNOWN P4-01 CORRECTNESS DEFECT: NONE
FORMAL CLOSURE: APPROVED BY PROJECT OWNER
P4-02+: NOT AUTHORIZED / NOT STARTED
PHASE 4 FORMAL CLOSURE: NOT AUTHORIZED
Git Promotion: NOT AUTHORIZED
Deployment: NOT AUTHORIZED
```

No detailed frozen P4-01 contract existed in the roadmap or repository governance sources. The minimum bounded contract is frozen in `docs/P4_01_BUILDERS_FETCHERS_DOMAIN_CONTRACT.md`, Contract ID `P4_01_BUILDERS_FETCHERS_DOMAIN_V1`, SHA-256 `e6cded902fb3dff14404d5d688edd1f8c423cdddad425c8f42873f2c624bae6f`. Fetchers own provider transport and provider-specific retrieval/normalization; builders own domain assembly and existing cache/composition policy. Existing public payload, provider date, error, cache, source-role, score, Decision, Outcome, P2 and P3 semantics remain unchanged.

The audit found 13 direct generic transport/request operations across eight builder functions, including a Barchart cookie-backed `Request` built and sent by the builder using a live opener returned from the fetcher. These operations now use named provider fetchers in `fetchers.py`. Barchart cookie/XSRF handling and the Deribit/Bybit provider normalization functions are contained in the fetcher boundary. TWSE/TPEx and Yahoo quote-page paths likewise use named adapters. `builders.py` has no calls that instantiate or invoke HTTP transport or generic `fetch_json` / `fetch_text`; an AST regression guards this boundary. Routes and app assembly continue through the existing builder/service paths; no route-level provider bypass was found in the audited paths.

The focused command `python -B -m unittest regression.test_p401_builders_fetchers_domain regression.test_p2_backend_boundaries regression.test_fetch_registry_bom regression.test_data_source_contracts regression.test_p203_source_provenance regression.test_p1_01_data_quality_remediation` passed 47 tests. `python -B -m unittest test_derivatives_platform` passed 206 tests. P4-01 fixtures cover named adapter URLs/timeouts, Barchart cookie/XSRF request containment, normalized Deribit/Bybit outputs, empty/error behavior, malformed provider responses, invalid numeric contracts, provider failure propagation, deterministic repeated outputs, and the builder transport boundary. In-memory Python syntax validation passed for `app.py`, `builders.py`, `fetchers.py`, `test_derivatives_platform.py`, and `regression/test_p401_builders_fetchers_domain.py`; `git diff --check` passed.

No live provider verification was required or performed. P4-01 did not open or mutate the authoritative Decision/Outcome database; no database schema, Decision, Outcome, forecast, model, score, probability, strategy, regime, market-time, fallback, or supplement semantics were changed. Project Owner formally accepted and closed P4-01; the closure record is `docs/P4_01_FORMAL_CLOSURE.md`. P4-02 and later nodes remain unauthorized and unstarted.

## Phase 4 Formal Closure Audit (2026-10-03)

```text
PHASE 4 FORMAL CLOSURE: BLOCKED
REASON: AUTHORITATIVE REQUIRED-NODE INVENTORY / ACCEPTANCE GATE NOT ESTABLISHED
P4-01: CLOSED (PRESERVED)
P4-02+: NOT AUTHORIZED / NOT STARTED (PRESERVED)
```

The repository-wide governance search found no frozen aggregate Phase 4 contract, approved node inventory, or Phase 4 completion criteria. `docs/MARKET_PLATFORM_INVESTMENT_DECISION_AUDIT.md` §19 places four engineering workstreams under Phase 4's recommended sequence: builders/fetchers domain separation; shared-calc global-state removal; giant page-module splitting; and Quant CI unification. Only the first has a closed node contract and closure record. The audit does not classify the remaining workstreams as optional or define their acceptance criteria, while this status record explicitly leaves P4-02+ not authorized / not started. The remaining workstream names are recorded as unresolved Phase 4 scope; no unsupported P4-02/P4-03/P4-04 contract identities or node states are inferred. Phase 4 closure is therefore not eligible without resolving the scope, and no Phase 4 PASS closure artifact was created.

This governance blocker does not reopen P4-01. No implementation, database, test, Git promotion, or deployment action was performed.

## P4-02 Shared-calc Hidden Global State — Execution (2026-10-03)

```text
P4-01: CLOSED (PRESERVED)
P4-02: EXECUTION COMPLETE
P4-02 ENGINEERING: PASS
P4-02 HIDDEN GLOBAL SEMANTIC STATE: REMOVED / VERIFIED
P4-02 EXPLICIT INPUT CONTRACT: VERIFIED
P4-02 REPLAY / DETERMINISM: PASS
P4-02 FORMAL ACCEPTANCE: PENDING PROJECT OWNER
P4-03: NOT AUTHORIZED / NOT STARTED
P4-04: NOT AUTHORIZED / NOT STARTED
PHASE 4 FORMAL CLOSURE: NOT ELIGIBLE YET
GIT PROMOTION: NOT AUTHORIZED
DEPLOYMENT: NOT AUTHORIZED
```

The frozen contract is `docs/P4_02_SHARED_CALC_HIDDEN_GLOBAL_STATE_CONTRACT.md`, Contract ID `P4_02_SHARED_CALC_EXPLICIT_INPUT_V1`, SHA-256 `f00339c4020ee4c1be6e73811d55d23464f6a18d5af4074447928b47348c90e0`. The audit examined 466 function-like nodes in `js/shared-calc.js`. It identified six hidden semantic reads in `buildInstitutionalBacktestFramework`, all from the ambient `data` object (`marketInternationalIndexes`, `marketMacroFactors`, `marketVolatility`, and `marketOverview`). The function now receives `marketContext` explicitly; `analyzeTechnicalTheories` passes it through, and all six sanctioned page callers pass the context collected at the existing `twEtfState.getMarketBreadthContext` adapter boundary. The focused guard reports zero remaining hidden semantic accesses, zero justified ambient reads inside calculations, and zero semantic global writes. The affected calculation has no cache.

The calculation formulas are unchanged. The regression pins the explicit-input fixture at framework total score `59`, market layer score `56.607142857142854`, market state `Neutral`, and 100% market-layer coverage; with no context, existing missing-data behavior remains score `50` with 0% coverage and no global fallback. Mutating unrelated ambient market data leaves the result unchanged, while changing explicit market context changes the market layer as expected. Replay and backtest outputs are deterministic. Audit runs 1 and 2 produced the same source SHA-256 `ac3cf6fe2d77dd7dc6d6bff75c89a9e28a12010d66c6800bb5c0edfc73a4628f` and fingerprint `e2f2c07c5b7fdae21476a03f88c672aecf18b819298821f1cda363cbba57fec8`.

The local Classic fallback and full-site ESM assets were rebuilt from the current source using the repository build tools so both runtime paths include the explicit-input change. Classic version: `td18-minify-65361d88eb8686ae`; ESM version: `td02-full-esm-0f47d0e4d4e6b961`. The TD-18 deterministic artifact/wiring verifiers passed. The TD-02 browser canary passed 42 runs across 21 pages (normal ESM and Classic fallback); its API fixtures were local HAR files and it did not change the frontend baseline. This is local artifact generation and verification only; no deployment occurred.

Regression evidence: `node regression/test_p402_shared_calc_hidden_global_state.js` passed twice with identical fingerprints; `node regression/test_p2_frontend_contract.js`, `node regression/test_q5_quant_math.js`, `node regression/test_p1c_sharpe_return_semantics.js`, `node regression/test_p0b1_futures_backtest_cost_wiring.js`, and `node regression/test_q2_backtest_methodology.js` passed; `python -B -m unittest regression.test_p401_builders_fetchers_domain` passed 10 tests. Syntax checks passed for 13 JavaScript source/test/Classic bundle files and the ESM module. `node regression/td02_full_esm_build.js --print-version` matched the generated ESM version. `python -B regression/td18_minify_verify.py`, `python -B regression/td18_shadow_verify.py`, and `python -B regression/td02_full_esm_canary.py` passed. `git diff --check` passed. The Q2 test fixture was minimally specified as `TW_EQUITY` after confirming at HEAD that its former unspecified asset class failed the existing fail-closed cost gate; all existing Q2 assertions remain.

No authoritative Decision/Outcome database was opened or mutated. P4-01 remains closed and its domain regression passed; the P4-01 builder/fetcher boundary was not changed. The earlier Phase 4 scope audit remains a dated historical record; the subsequent Project Owner authorization froze the four-node inventory and authorized P4-02. P4-03 and P4-04 remain unstarted and unauthorized, so Phase 4 formal closure is still not eligible. The size of `shared-calc.js` and any orphaned calculation inventory remain outside P4-02. No Git promotion, live-provider call, or deployment occurred.

## P4-02 Formal Acceptance / Closure (2026-10-03)

```text
P4-01: CLOSED
P4-02: CLOSED
P4-02 RESULT: PASS — ENGINEERING / GOVERNANCE CLOSURE
P4-02 FORMAL ACCEPTANCE: APPROVED BY PROJECT OWNER
P4-03: NOT AUTHORIZED / NOT STARTED
P4-04: NOT AUTHORIZED / NOT STARTED
PHASE 4 FORMAL CLOSURE: NOT ELIGIBLE YET
GIT PROMOTION: NOT AUTHORIZED
DEPLOYMENT: NOT AUTHORIZED
```

Formal closure evidence: `docs/P4_02_FORMAL_CLOSURE.md`. The frozen contract remains unchanged (SHA-256 `f00339c4020ee4c1be6e73811d55d23464f6a18d5af4074447928b47348c90e0`); accepted P4-02 source/fingerprint evidence remains attributable. No source, test, baseline, database, deployment, or Git promotion changes were made during formal closure.

## P4-03 Giant Page Modules Decomposition — Execution (2026-10-03)

```text
P4-01: CLOSED (PRESERVED)
P4-02: CLOSED (PRESERVED)
P4-03: EXECUTION COMPLETE
P4-03 ENGINEERING: PASS
P4-03 GIANT PAGE MODULES: DECOMPOSED / VERIFIED
P4-03 CLASSIC / ESM RUNTIME PARITY: PASS
P4-03 FORMAL ACCEPTANCE: PENDING PROJECT OWNER
P4-04: NOT AUTHORIZED / NOT STARTED
PHASE 4 FORMAL CLOSURE: NOT ELIGIBLE YET
GIT PROMOTION: NOT AUTHORIZED
DEPLOYMENT: NOT AUTHORIZED
```

The frozen contract is `docs/P4_03_GIANT_PAGE_MODULES_DECOMPOSITION_CONTRACT.md`, Contract ID `P4_03_GIANT_PAGE_MODULES_DECOMPOSITION_V1`, SHA-256 `9ec9a9905ad697ce696e40c6ec8e9742e28f2af06541dbc39008ad213215b96b`. The contract froze the minimum structural scope before implementation; its generated-wiring clarification is limited to builder-generated cache-busting query values and runtime manifest/cache versions explicitly allowed by the Owner authorization.

The selected target was `js/page-global-market-assethub.js` (pre-split working-tree SHA-256 `ac326185a3455a18256597c91c0b9f8bc877f817459638b8d3e762b786684a62`, 423,499 bytes, 145 function declarations, 6,767 lines by the frozen inventory convention). It combined shared market/quote helpers, finance analytics, derivatives analytics/strategy-engine code, and asset-hub composition. The entry is now 460 lines / 7 functions. Three responsibility modules were added: shared helpers 616 lines / 36 functions; asset-finance 3,785 lines / 79 functions; derivatives 1,909 lines / 23 functions. The 138 moved function bodies match the contract fingerprints; the `strategyEngine` top-level assignment remains byte-identical in the derivatives module. Source bytes across all four outputs total 423,499, equal to the pre-split source. The structural/parity regression reports fingerprint `10ddd7fd506912fb06f3972d7d3d94ae3898c1bfb9d023348e541e41ab1537f8` on two runs.

`market_config.JS_MODULE_STATIC_FILES` and both TD-18 source locks include the new files. The options-to-entry dependency for Taiwan option-chain rendering was removed by moving the helper family into the shared module. No new module cycle was introduced; the pre-existing futures/options cross-page cycle remains. The P4-03 regression checks single ownership of all 145 functions, exact function-body fingerprints, the strategy-engine assignment fingerprint, lock/allowlist order, runtime dependency order, and representative data/render output. Existing strategy tests now read the new derivatives owner file. The point-in-time regression also uses an injected fixed clock so its frozen September 25, 2026 fixture remains fresh and deterministic; assertions were not weakened.

Local Classic assets were regenerated by the locked TD-18 builder (version `td18-minify-75a73bfba6836641`). Full-site ESM assets were regenerated by the existing TD-02 builder (version `td02-full-esm-7c8021c06d4cbbaf`, 895 bridge symbols). Generated loader/cache query references and manifests were updated; API, visual, and interaction baselines were not changed. `python -B regression/td18_minify_verify.py` passed; `python -B regression/td18_shadow_verify.py` passed with 895 symbols, 21 pages, and zero local-asset 404s; `python -B regression/td02_full_esm_canary.py` passed 21 pages / 42 runs across normal ESM and Classic rollback modes.

Focused regressions passed: `node regression/test_p403_giant_page_modules_decomposition.js` twice with the same fingerprint; `node regression/test_p402_shared_calc_hidden_global_state.js`; `node regression/test_p2_frontend_contract.js`; `node regression/test_derivatives_analytics_wiring.js`; `node regression/test_options_strategy_analyzer.js`; `node regression/test_p1_04_no_trade_ui_gates.js`; `node regression/test_p1_options_execution.js`; `node regression/test_p1_options_liquidity.js`; `node regression/test_p1_point_in_time.js`; `node regression/test_q5_quant_math.js`; `node regression/test_p0b1_futures_backtest_cost_wiring.js`; and `node regression/test_q2_backtest_methodology.js`. `python -B -m unittest regression.test_p401_builders_fetchers_domain` passed 10 tests. Syntax checks passed for 13 changed JavaScript source/test files. `git diff --check` passed after implementation. P4-01's builder/fetcher boundary and P4-02's explicit-input contract remain unchanged; no authoritative database was accessed or mutated. No P4-04 work, Git promotion, or deployment occurred.

## P4-03 Giant Page Modules — Formal Acceptance / Closure (2026-10-03)

```text
P4-01: CLOSED (PRESERVED)
P4-02: CLOSED (PRESERVED)
P4-03: CLOSED
P4-03 RESULT: PASS — ENGINEERING / GOVERNANCE CLOSURE
P4-03 GIANT PAGE MODULES: DECOMPOSED / VERIFIED
P4-03 RESPONSIBILITY BOUNDARIES: VERIFIED
P4-03 CLASSIC / ESM RUNTIME PARITY: PASS
P4-03 KNOWN CORRECTNESS DEFECT: NONE
P4-03 FORMAL ACCEPTANCE: APPROVED BY PROJECT OWNER
P4-04: NOT AUTHORIZED / NOT STARTED
PHASE 4 FORMAL CLOSURE: NOT ELIGIBLE YET
GIT PROMOTION: NOT AUTHORIZED
DEPLOYMENT: NOT AUTHORIZED
```

Closure evidence: `docs/P4_03_FORMAL_CLOSURE.md`, SHA-256 `2232022285aa86b6bf4974b7dc5b5faf068f3eddfd651d0ff429a900fc7f4241`. The frozen P4-03 contract SHA-256 remains `9ec9a9905ad697ce696e40c6ec8e9742e28f2af06541dbc39008ad213215b96b`. The P4-03 structural/parity regression freshly reproduced the accepted fingerprint `10ddd7fd506912fb06f3972d7d3d94ae3898c1bfb9d023348e541e41ab1537f8`; the P4-02 and P4-01 compatibility regressions passed. TD-18 minify and shadow verification passed, including 21 pages, 895 symbols, and zero local asset 404s. The accepted ESM canary remains attributable to unchanged version `td02-full-esm-7c8021c06d4cbbaf` (21 pages / 42 runs); it was not rerun during closure. No authoritative DB access or mutation, P4-04 work, Git promotion, or deployment occurred. P4-04 remains unauthorized, so Phase 4 remains incomplete.

## P4-04 Quant CI / Orphan Regression Cleanup — Execution (2026-10-03)

```text
P4-01: CLOSED (PRESERVED)
P4-02: CLOSED (PRESERVED)
P4-03: CLOSED (PRESERVED)
P4-04: EXECUTION COMPLETE
P4-04 ENGINEERING: PASS
P4-04 QUANT REGRESSION INVENTORY: VERIFIED
P4-04 QUANT CI COVERAGE: VERIFIED
P4-04 MANDATORY ORPHAN REGRESSIONS: 0
P4-04 CI FAILURE PROPAGATION: VERIFIED
P4-04 KNOWN CORRECTNESS / COVERAGE DEFECT: NONE
P4-04 FORMAL ACCEPTANCE: PENDING PROJECT OWNER
PHASE 4 FORMAL CLOSURE: NOT ELIGIBLE YET
GIT PROMOTION: NOT AUTHORIZED
DEPLOYMENT: NOT AUTHORIZED
NEXT PHASE: NOT AUTHORIZED
```

The frozen contract is `docs/P4_04_QUANT_CI_ORPHAN_REGRESSION_CONTRACT.md`, Contract ID `P4_04_QUANT_CI_ORPHAN_REGRESSION_V1`, SHA-256 `1c29612d28801cc3787ebe7794994f6f0f323f1ff13d02fbafc0effe9946df65`. The inventory is `docs/P4_04_QUANT_REGRESSION_INVENTORY.md`, SHA-256 `3ad061c47fe0d96d60e5d29cc52788f07d354a9cf2a2978ebc67cc53045690c4`. The frozen manifest contains 37 mandatory quantitative regressions (23 Python unittest suites and 14 Node scripts) and records nine adjacent candidates as out of scope. The audit found seven prior direct P1/P2 workflow invocations; the P1 direct Q5 command was consolidated into the runner, six independent P2 direct paths remain, and all 37 mandatory tests have a deterministic P1 Quant runner path. The final classification is 6 CI-enforced direct, 31 CI-enforced via suite, and zero orphan. No regression was retired.

`python -B regression/run_quant_regressions.py` passed all 37 entries: 431 unittest cases across 23 Python suites plus 14 Node scripts. `python -B -m unittest regression.test_p404_quant_ci_coverage` passed 9 tests, including exact manifest and inventory coverage, workflow wiring, no failure suppression, Q2 invariant preservation, isolated historical-replay DB guarding, and propagation of a controlled child exit code 23. Workflow YAML parsing passed; a read-only existence audit found all 36 explicitly enumerated workflow script/module file references. Compatibility checks passed: `python -B -m unittest regression.test_p401_builders_fetchers_domain` (10 tests), `node regression/test_p402_shared_calc_hidden_global_state.js`, and `node regression/test_p403_giant_page_modules_decomposition.js`. `node regression/test_q2_backtest_methodology.js` passed with chronology, execution timing, effective sample, and cost assertions intact. No quantitative formula, model contract, target, feature, horizon, cost rule, score mapping, database schema/data, or API/visual baseline was changed by P4-04.

The P2-03 historical replay test's no-touch guard uses a temporary sentinel under an isolated patched root. The Quant runner points database/cache environment variables at a temporary directory; no authoritative SQLite database or live provider was accessed. P4-04 records execution completion only. Formal acceptance remains pending Project Owner; this entry does not close P4-04 or authorize Phase 4 closure, Git promotion, deployment, or a later phase.

## P4-04 Formal Acceptance / Closure (2026-10-03)

```text
P4-01: CLOSED
P4-02: CLOSED
P4-03: CLOSED
P4-04: CLOSED
P4-04 RESULT: PASS — ENGINEERING / GOVERNANCE CLOSURE
P4-04 QUANT REGRESSION INVENTORY: VERIFIED
P4-04 QUANT CI COVERAGE: VERIFIED
P4-04 MANDATORY ORPHAN REGRESSIONS: 0
P4-04 CI FAILURE PROPAGATION: VERIFIED
P4-04 KNOWN CORRECTNESS / COVERAGE DEFECT: NONE
P4-04 FORMAL ACCEPTANCE: APPROVED BY PROJECT OWNER
PHASE 4 NODE COMPLETION: 4 / 4 CLOSED
PHASE 4 FORMAL CLOSURE: ELIGIBLE / NOT YET EXECUTED
GIT PROMOTION: NOT AUTHORIZED / NOT EXECUTED
DEPLOYMENT: NOT AUTHORIZED / NOT EXECUTED
NEXT PHASE: NOT AUTHORIZED / NOT STARTED
```

Formal closure record: `docs/P4_04_FORMAL_CLOSURE.md`, SHA-256 `57de898da02f3df602e6428899d04039aa17c1425330307abed8800ed6d00da6`. The frozen contract and inventory remain byte-identical to their accepted hashes (`1c29612d28801cc3787ebe7794994f6f0f323f1ff13d02fbafc0effe9946df65` and `3ad061c47fe0d96d60e5d29cc52788f07d354a9cf2a2978ebc67cc53045690c4`). The accepted Quant runner result remains attributable to the unchanged 37-test manifest and execution sources; full Quant regression was not rerun during formal closure. The coverage regression had 9 passing tests, including controlled exit-code-23 propagation. Workflow path audit is 36 / 36; prior YAML parse evidence remains applicable because the workflow was unchanged. Markdown hard-break whitespace is limited to the two intentional spaces on contract lines 3–4 and inventory lines 3–6; tracked `git diff --check` passes and does not inspect untracked Markdown files.

P4-04 closes the fourth Phase 4 node only. Phase 4 Formal Closure has not been executed and requires separate Project Owner authorization. No Git promotion, deployment, or subsequent phase work occurred.

## Phase 4 Formal Closure (2026-10-03)

```text
P4-01: CLOSED
P4-02: CLOSED
P4-03: CLOSED
P4-04: CLOSED
PHASE 4 NODE COMPLETION: 4 / 4 CLOSED
PHASE 4: CLOSED
RESULT: PASS — ENGINEERING / GOVERNANCE CLOSURE
GIT PROMOTION: NOT AUTHORIZED / NOT EXECUTED
DEPLOYMENT: NOT AUTHORIZED / NOT EXECUTED
NEXT PHASE: NOT AUTHORIZED / NOT STARTED
```

Formal closure evidence: `docs/PHASE4_FORMAL_CLOSURE.md`, SHA-256 `5344eacdac03fcd8c88d67a8d3cdd6a7b9bfff337f138e48c616820845f0db66`. Phase 4's authoritative scope remains exactly P4-01 through P4-04. The four node contracts and formal closure artifacts match their authorized hashes; P4-04 inventory remains 37 mandatory tests with zero orphans. This closes Phase 4's engineering / governance scope only. It makes no predictive, profitability, trading-edge, statistical-significance, calibration-maturity, or model-stability claim, and does not alter P2/P3 evidence status. No authoritative database mutation, Git promotion, deployment, or later-phase work occurred.

## Phase 3 Formal Closure (2026-10-03)

```text
P3-01: CLOSED
P3-01 STATISTICAL EVIDENCE: NOT YET MATURE
P3-02: CLOSED
P3-02 REALIZED REGIME STATISTICAL EVIDENCE: NOT AVAILABLE
P3-03: CLOSED
P3-03 AUTHORITATIVE NET EXPECTANCY: NOT AVAILABLE
P3-03 PROFITABILITY / MODEL VALIDITY: NOT ESTABLISHED
P3-04: CLOSED
P3-04 AUTHORITATIVE DRIFT EVIDENCE: NOT AVAILABLE
P3-04 MODEL STABILITY: NOT ESTABLISHED
PHASE 3 NODE COMPLETION: 4 / 4 CLOSED
PHASE 3: CLOSED
RESULT: PASS — ENGINEERING / GOVERNANCE CLOSURE
probabilityLabelAllowed: false
AUTHORITATIVE DB MUTATION: NONE
GIT PROMOTION: NOT EXECUTED
DEPLOYMENT: NOT AUTHORIZED / NOT EXECUTED
NEXT PHASE: NOT AUTHORIZED / NOT STARTED
```

Formal closure evidence: `docs/PHASE3_FORMAL_CLOSURE.md`, SHA-256 `1c15d7145b2d04ba0f85e0921834e2e7ff4dd95dc8f29aabc4362c446f0b8372`. The parent Phase 3 contract remains byte-identical (SHA-256 `43ebcad66cd8267c07bca2419fbbcdeca066e6195eecf1e4ac782fd5954bbc57`); P3-02, P3-03, and P3-04 contracts and the P3-03 / P3-04 closure records match their accepted identities. The accepted ledger evidence remains one Decision and zero Outcomes; eligible matured labels, prospective forecasts, valid OOS pairs, cost-qualified observations, and sufficient temporal observations remain unavailable or zero as recorded by their node evidence. This is engineering/governance closure only and does not upgrade statistical evidence or probability governance. Phase 1, Phase 2, and the already-closed Phase 4 remain unchanged.
