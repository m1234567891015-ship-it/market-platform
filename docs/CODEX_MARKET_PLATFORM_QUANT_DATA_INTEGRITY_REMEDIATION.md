# MARKET-PLATFORM — Quant / Data Integrity Remediation Work Order for Codex

**Document type:** Codex execution specification  
**Project:** `market-platform`  
**Source:** Read-only engineering + investment-decision audit of the supplied project snapshot  
**Owner:** Project Owner / User  
**Priority:** Data integrity and quantitative correctness before feature expansion  
**Execution principle:** Minimum necessary change; preserve existing public contracts unless explicitly required below.

---

## 0. OWNER AUTHORITY / EXECUTION BOUNDARY

This work order authorizes Codex to implement **only the remediation items explicitly defined in this document**.

### Allowed

- Read and inspect the current repository.
- Modify code, tests, and internal documentation only as required to satisfy the acceptance criteria in this work order.
- Add focused regression tests required to prove each remediation.
- Refactor the smallest necessary internal units when required for correctness.
- Run local tests and report exact evidence.

### Prohibited unless separately authorized by the Project Owner

- Adding unrelated features.
- Adding new technical-analysis indicators merely for feature expansion.
- Changing unrelated UI/UX.
- Reordering, merging, splitting, or redefining any existing frozen owner workflow.
- Broad architectural rewrites.
- Changing external API contracts unless this work order explicitly requires it.
- Changing deployment configuration.
- Deploying.
- Creating or modifying cloud resources.
- Sending network-side changes to production.
- Committing, pushing, opening PRs, merging, tagging, or releasing.
- Declaring production PASS without production evidence.
- Advancing automatically to another project phase after this work order is complete.

**FAIL CLOSED:** If repository evidence conflicts with this document, stop that item and report the conflict. Do not invent a replacement design.

**HARD STOP:** When all authorized items are complete and evidence is reported, stop.

---

# 1. OBJECTIVE

Improve the platform's investment-decision reliability by correcting data-time semantics, futures execution-cost assumptions, portfolio risk metrics, and decision outcome traceability.

The priority order is:

1. **P0-A — Market date / time semantic integrity**
2. **P0-B — Futures contract multiplier and execution-cost integrity**
3. **P1-A — Portfolio VaR correction**
4. **P1-B — Portfolio risk contribution correction**
5. **P1-C — Sharpe / return metric semantic correction**
6. **P1-D — Decision provenance and outcome ledger**
7. **P2-A — Large-module technical-debt containment**

Do not begin P2-A until P0/P1 correctness work is complete and passing.

---

# 2. P0-A — MARKET DATE / TIME SEMANTIC INTEGRITY

## 2.1 Problem

Audit evidence identified a path where Yahoo-derived futures data can fall back to the machine's current calendar date when the upstream market-data timestamp cannot be parsed.

Observed logic included a fallback equivalent to:

```python
if not quote_date:
    quote_date = datetime.now(app.TZ).strftime("%Y-%m-%d")
```

That fallback can turn a retrieval/observation date into a market trading date.

A downstream builder may then compare that synthetic date with TAIFEX data and allow the Yahoo result to supersede official exchange data.

The persisted value may subsequently be written to fields such as `trade_time` / `trade_date`.

This can create weekend or holiday market records and contaminate:

- freshness checks,
- point-in-time logic,
- time-series ordering,
- analytics,
- historical comparisons,
- backtests,
- model features,
- decision evidence.

## 2.2 Required semantic model

Do not treat these timestamps as interchangeable:

- `market_as_of`  
  Timestamp/date at which the market price is valid.

- `source_updated_at`  
  Timestamp explicitly supplied by the upstream provider, when available.

- `observed_at`  
  Timestamp when this application retrieved or observed the response.

### Mandatory rule

> Unknown `market_as_of` MUST NOT be replaced with `observed_at`.

If the upstream provider does not expose a valid market timestamp, preserve that uncertainty explicitly.

## 2.3 Required implementation behavior

Codex must:

1. Trace the complete Yahoo futures parsing → builder selection → persistence path.
2. Remove any fallback that converts the current system date into a market trading date.
3. Preserve retrieval time separately where needed.
4. Ensure a quote with unknown market date cannot outrank or overwrite a quote whose official market date is known solely because the retrieval date is newer.
5. Prefer authoritative exchange data when source timestamps conflict and no stronger explicit rule already exists.
6. Preserve existing API response compatibility where possible.
7. If a public field currently conflates observation time and market time, introduce the smallest backward-compatible correction possible.
8. Do not manufacture exchange trading dates from weekday assumptions alone.

## 2.4 Required regression coverage

Add tests covering at minimum:

### Case A — Weekend retrieval

- System date: Saturday.
- Yahoo payload contains price but no valid market date.
- TAIFEX payload contains a valid prior trading date.
- Expected:
  - Yahoo `observed_at` may be Saturday.
  - Yahoo `market_as_of` remains unknown.
  - persisted market trade date is not Saturday.
  - TAIFEX official dated record is not superseded merely because Yahoo was retrieved later.

### Case B — Valid Yahoo market timestamp

- Yahoo exposes an explicit valid trading timestamp.
- Expected:
  - parser preserves it.
  - comparison uses actual market time, not retrieval time.

### Case C — Conflicting known dates

- Both sources expose explicit market timestamps.
- Expected:
  - selection follows deterministic source-precedence/freshness rules.
  - no machine-clock substitution occurs.

### Case D — Persistence

- Verify database `trade_date` / `trade_time` represents market time only.
- Verify retrieval timestamp, if persisted, is stored separately.

## 2.5 Acceptance criteria

PASS only if:

- No market date is fabricated from the machine's current date.
- Weekend/holiday retrieval cannot create a false trading date through this path.
- Existing regression suite remains green.
- New regression tests demonstrate the failure before the fix or otherwise prove the corrected behavior.
- Exact modified files and test commands are reported.

---

# 3. P0-B — FUTURES CONTRACT MULTIPLIER / EXECUTION COST INTEGRITY

## 3.1 Problem

The current futures cost path was observed with zero/default assumptions similar to:

```text
commissionPerContract = 0
levyPerContract       = 0
slippageTicks         = 0
multiplier            = 1
```

The backtest-building path also contained explicit `multiplier: 1` assignments that can override a correct multiplier supplied by the caller.

This can materially understate trading friction and distort:

- net return,
- expectancy,
- profit factor,
- strategy ranking,
- drawdown,
- risk/reward analysis,
- decision quality.

## 3.2 Required design

Create or reuse a single authoritative contract-specification layer.

At minimum it must support:

- symbol / product identifier,
- contract multiplier,
- tick size,
- transaction tax / levy where applicable,
- commission assumption,
- slippage assumption,
- currency if relevant,
- effective-date/version metadata if the existing architecture supports it.

Do not duplicate contract constants across unrelated modules.

## 3.3 Required behavior

Codex must:

1. Trace futures contract parameters from input to final backtest execution.
2. Remove forced `multiplier: 1` behavior where it incorrectly overrides the instrument specification.
3. Ensure the execution-cost function receives the actual product multiplier.
4. Ensure non-zero user/configured costs survive all intermediate model-building layers.
5. Keep zero cost only when explicitly configured as zero.
6. Do not silently substitute `1` for a missing economically material multiplier.

### Fail-closed requirement

If a futures instrument requires a multiplier and the multiplier cannot be resolved:

- do not silently compute an apparently valid net P&L using multiplier `1`;
- return an explicit unavailable/error state consistent with existing error conventions, or prevent the backtest from claiming valid net results.

## 3.4 Required tests

At minimum:

### Case A — Caller multiplier preservation

Input:

```text
multiplier = 50
```

Expected:

- the final execution-cost calculation receives `50`;
- no intermediate layer resets it to `1`.

### Case B — Non-zero friction

Input:

- non-zero commission,
- non-zero levy/tax,
- non-zero slippage ticks,
- valid multiplier.

Expected:

- gross P&L > net P&L for a profitable trade, all else equal;
- exact cost arithmetic is deterministic.

### Case C — Missing multiplier

Expected:

- fail closed;
- no valid-looking net performance result using multiplier `1`.

### Case D — Existing instrument behavior

Existing supported futures instruments must retain deterministic behavior and existing API shape unless a correctness change is explicitly necessary.

## 3.5 Acceptance criteria

PASS only if:

- multiplier survives end-to-end;
- cost assumptions survive end-to-end;
- missing critical contract economics cannot silently become `1`/zero;
- focused regression tests pass;
- existing quantitative-integrity regressions remain green.

---

# 4. P1-A — PORTFOLIO VaR CORRECTION

## 4.1 Problem

The portfolio page currently labels a value as:

> 95% single-day VaR

but the audited calculation is conceptually equivalent to:

```text
average absolute current stock move
× portfolio value
× 1.65
```

This is not a standard portfolio VaR methodology.

It does not properly model the historical portfolio return distribution or covariance structure.

## 4.2 Required methodology

Implement **Historical VaR 95%** as the default unless an existing documented project contract requires another methodology.

### Required calculation

1. Obtain synchronized daily return history for portfolio constituents.
2. Apply portfolio weights to produce portfolio daily return series.
3. Use a deterministic historical 5th-percentile loss estimate for 95% one-day VaR.
4. Express:
   - VaR amount,
   - VaR percentage.
5. Clearly define sign/display convention.

Recommended:

```text
VaR95 = max(0, -Q_5%(portfolio_daily_returns))
```

Then:

```text
VaR95_amount = portfolio_value × VaR95
```

## 4.3 Expected Shortfall

If sufficient historical data exists, also compute:

```text
ES95 = average loss among observations at or beyond the VaR95 tail
```

If adding ES would require significant unrelated UI work, implement calculation/domain support first and report UI as unchanged.

## 4.4 Data sufficiency

Do not fabricate VaR when history is insufficient.

Define a documented minimum-sample threshold.

If the threshold is not met:

```text
VaR = unavailable
reason = insufficient_history
```

Use existing UI unavailable conventions where possible.

## 4.5 Required tests

Cover:

- deterministic synthetic return series with known 5th percentile;
- insufficient history;
- missing constituent history;
- mixed weights;
- no-lookahead chronological alignment;
- portfolio value scaling;
- stable result across repeated runs.

## 4.6 Acceptance criteria

PASS only if:

- the label `95% one-day VaR` maps to a real documented VaR calculation;
- the old `avgMove × 1.65` heuristic is no longer presented as VaR;
- insufficient data does not create pseudo-precision;
- tests prove the math.

---

# 5. P1-B — PORTFOLIO RISK CONTRIBUTION CORRECTION

## 5.1 Problem

Current risk contribution was observed to approximate:

```text
weight × individual volatility
```

and normalize those values.

That ignores cross-asset covariance and therefore is not standard marginal/Euler portfolio risk contribution.

## 5.2 Required methodology

For portfolio weights `w` and covariance matrix `Σ`:

```text
portfolio_variance = w' Σ w
portfolio_volatility = sqrt(w' Σ w)
marginal_risk_i = (Σw)_i / portfolio_volatility
risk_contribution_i = w_i × marginal_risk_i
```

Equivalent form:

```text
RC_i = w_i (Σw)_i / σ_p
```

Percentage contribution:

```text
RC_pct_i = RC_i / sum(RC)
```

Handle floating-point tolerance deterministically.

## 5.3 Required tests

Cover:

- perfectly correlated assets;
- low/negative correlation;
- single-asset portfolio;
- unequal weights;
- covariance matrix with valid deterministic fixture;
- sum of component risk contributions reconciles with total portfolio volatility within tolerance.

## 5.4 Acceptance criteria

PASS only if:

- covariance participates in risk attribution;
- component contribution reconciliation is tested;
- existing portfolio-volatility behavior is not regressed.

---

# 6. P1-C — SHARPE / RETURN METRIC SEMANTIC CORRECTION

## 6.1 Problem

A portfolio metric was observed as conceptually:

```text
netReturn / avgMove
```

while being described as Sharpe-like.

The numerator and denominator use incompatible horizons and the metric is not a Sharpe Ratio.

A separate backtest area already correctly distinguishes a custom return-to-dispersion score from Sharpe.

## 6.2 Required behavior

Codex must choose the smallest correct solution:

### Preferred

Implement an actual Sharpe Ratio using synchronized periodic portfolio returns:

```text
excess_return_t = portfolio_return_t - risk_free_periodic_t
Sharpe = mean(excess_return) / stdev(excess_return)
```

Annualize only when the return frequency is known and documented.

### Acceptable fallback

If a valid Sharpe cannot be supported with current data:

- remove the Sharpe naming;
- rename the existing metric to an explicit non-standard descriptive name;
- document exactly what it measures.

Do not call a cross-sectional/current-move ratio a Sharpe Ratio.

## 6.3 Additional semantic correction

Review any `expectedReturn60`-style field.

If it represents realized trailing 60-day return/momentum rather than a forecast:

- rename internally and/or in UI to reflect historical momentum / trailing return;
- do not call realized trailing return an expected return.

Preserve public compatibility if necessary through deprecation/aliasing rather than silently changing API semantics.

## 6.4 Acceptance criteria

PASS only if:

- no non-Sharpe formula is presented as Sharpe;
- realized trailing return is not misrepresented as expected return;
- tests cover new formula/label behavior.

---

# 7. P1-D — DECISION PROVENANCE + OUTCOME LEDGER

## 7.1 Existing strength to preserve

The current derivatives analytics design already contains important decision provenance concepts such as:

- `decision_id`,
- input snapshot hash,
- model/strategy version,
- evidence score,
- data quality score,
- explicit distinction between evidence and calibrated predictive confidence.

Do not weaken those semantics.

## 7.2 Problem

The persisted AI analysis/report layer does not appear to retain the full decision provenance and later realized outcome required for honest model evaluation.

Without an append-only decision/outcome history, the system cannot reliably answer:

- Which signals work by market regime?
- Which strategy version improved?
- Was a recommendation profitable after cost?
- What were MFE and MAE?
- Was the stop/target reached?
- Is confidence actually calibrated?

## 7.3 Required implementation

Add a minimal append-only decision ledger using the existing database architecture and migration conventions.

### Decision record — minimum fields

Use existing names/contracts where available rather than duplicating them.

Minimum logical content:

- decision ID,
- created/observed timestamp,
- market-as-of timestamp,
- instrument,
- strategy identifier,
- strategy/model version,
- input snapshot hash,
- evidence score,
- data quality score,
- predictive confidence only if genuinely calibrated,
- entry/reference price,
- relevant execution-cost assumptions,
- source/provenance metadata sufficient to reproduce the decision.

### Outcome record — minimum fields

Do not overwrite the historical decision.

Append/update a separate outcome entity keyed to decision ID with:

- evaluation horizon,
- evaluation timestamp,
- realized net return,
- MFE,
- MAE,
- target hit if applicable,
- stop hit if applicable,
- available/unavailable reason,
- cost-adjusted result,
- data-quality state.

### Suggested horizons

Support the existing platform conventions if already defined.

Otherwise use clearly parameterized horizons rather than hard-coding business meaning throughout the codebase.

Examples may include:

- T+1,
- T+5,
- T+20.

Do not claim predictive calibration merely because these rows exist.

## 7.4 Point-in-time requirement

Outcome calculation MUST NOT mutate the original decision snapshot.

Decision inputs must remain reproducible as they existed at decision time.

## 7.5 Required tests

Cover:

- append decision;
- duplicate decision ID protection/idempotency according to existing DB style;
- outcome linked to correct decision;
- original decision snapshot immutable;
- missing future price → unavailable, not fabricated;
- execution-cost-adjusted result;
- point-in-time chronology;
- deterministic query ordering.

## 7.6 Acceptance criteria

PASS only if:

- a historical decision can be reconstructed;
- a later outcome can be evaluated without rewriting decision-time evidence;
- provenance remains intact;
- no fake model-confidence field is introduced.

---

# 8. P2-A — LARGE-MODULE TECHNICAL-DEBT CONTAINMENT

## 8.1 Scope

Audit identified very large modules, including approximately:

- `builders.py` — ~7k lines,
- `fetchers.py` — ~5k lines,
- several frontend market/options/futures modules — multi-thousand-line files.

This is technical debt, but correctness work takes priority.

## 8.2 Authorization limit

This work order **does not authorize a broad rewrite**.

Codex may only extract code when:

- required to implement P0/P1 cleanly, or
- extraction is behavior-preserving and directly reduces the touched module's risk.

Potential domain boundaries include:

- TAIFEX,
- TWSE,
- U.S./global market,
- news/provider adapters,
- portfolio risk math,
- execution-cost / contract specifications.

## 8.3 Requirements

Any extraction must:

- preserve external contracts;
- preserve deterministic behavior;
- come with regression coverage;
- avoid mass renaming unrelated code;
- avoid formatting-only churn across large files.

## 8.4 Acceptance criteria

P2-A is complete for this work order when:

- P0/P1 changes do not further increase giant-module coupling;
- any required extraction is tested;
- no unrelated architecture rewrite occurred.

No requirement exists to fully split all large files in this work order.

---

# 9. PACKAGE HYGIENE — NON-BLOCKING CLEANUP

The supplied working ZIP contained generated/runtime artifacts such as:

- `__pycache__/`,
- `.pyc`,
- `debug.log`,
- local SQLite database,
- dependency/build artifacts such as `node_modules`.

The project already appears to contain exclusion logic for portable packaging.

## Required action

Verify the existing portable/package builder excludes runtime/generated artifacts.

Only fix it if the existing packaging path demonstrably includes files that its own policy intends to exclude.

Do not delete the user's working database from the repository/workspace merely because it appears in the supplied audit ZIP.

Add or update focused packaging tests only if necessary.

This section is lower priority than P0/P1.

---

# 10. TEST / VERIFICATION REQUIREMENTS

Codex must run the repository's existing relevant test suites plus all new focused regressions.

At minimum, preserve and re-run the available quantitative/integrity guards relevant to the modified areas, including equivalents of:

- quant integrity regression,
- backtest methodology,
- purged / embargo execution behavior,
- quant math,
- asset cost,
- futures/options execution,
- liquidity,
- point-in-time,
- strategy analyzer,
- security/static guardrails.

Do not claim a test PASS unless the command actually completed successfully.

If a dependency or environment limitation prevents a suite from running:

```text
STATUS: BLOCKED / NOT VERIFIED
```

and report:

- exact command,
- exact error,
- which acceptance criteria remain unverified.

Do not convert an environment failure into a project PASS or FAIL without evidence.

---

# 11. REQUIRED CODEX EXECUTION ORDER

Execute strictly in this order:

```text
P0-A
↓
P0-B
↓
P0 regression gate
↓
P1-A
↓
P1-B
↓
P1-C
↓
P1-D
↓
P1 regression gate
↓
P2-A only as required
↓
Package hygiene verification
↓
Full authorized regression verification
↓
Final report
↓
HARD STOP
```

If P0-A or P0-B fails acceptance:

- do not proceed to P1;
- report the blocker.

If a P1 item exposes a pre-existing unrelated defect:

- record it separately;
- do not repair it unless necessary to satisfy this work order.

---

# 12. REQUIRED FINAL REPORT FORMAT

Codex final output must use this structure:

```markdown
# MARKET-PLATFORM Quant/Data Integrity Remediation — Execution Report

## 1. Overall Status
PASS / PARTIAL / BLOCKED

## 2. P0-A Market Date Semantics
Status:
Files changed:
Behavior changed:
Tests:
Evidence:
Remaining risk:

## 3. P0-B Futures Contract / Cost Integrity
Status:
Files changed:
Behavior changed:
Tests:
Evidence:
Remaining risk:

## 4. P1-A Portfolio VaR
Status:
Formula implemented:
Minimum sample rule:
Tests:
Evidence:

## 5. P1-B Risk Contribution
Status:
Formula implemented:
Tests:
Reconciliation evidence:

## 6. P1-C Sharpe / Metric Semantics
Status:
Final metric semantics:
Tests:
Evidence:

## 7. P1-D Decision Outcome Ledger
Status:
Schema/migration:
Point-in-time behavior:
Tests:
Evidence:

## 8. P2-A Technical Debt
Changes made:
Changes intentionally not made:
Reason:

## 9. Package Hygiene
Status:
Evidence:

## 10. Regression Summary
Commands:
Passed:
Failed:
Blocked:
Skipped:

## 11. Changed Files
- exact file list

## 12. Unresolved Issues
- exact unresolved items only

## 13. Git / Deployment State
Commit created: NO unless separately authorized
Push performed: NO unless separately authorized
PR created: NO unless separately authorized
Merge performed: NO unless separately authorized
Deployment performed: NO unless separately authorized
```

---

# 13. DEFINITION OF DONE

This work order is complete only when all of the following are true:

- [ ] Unknown upstream market date is never silently replaced with retrieval date.
- [ ] Weekend/holiday retrieval cannot fabricate a trading date through the audited path.
- [ ] Futures multiplier is preserved end-to-end.
- [ ] Futures transaction-cost assumptions are preserved end-to-end.
- [ ] Missing critical futures contract economics fails closed.
- [ ] `95% one-day VaR` is backed by a legitimate documented VaR methodology.
- [ ] Portfolio risk contribution incorporates covariance.
- [ ] No non-Sharpe metric is presented as Sharpe.
- [ ] Historical trailing return is not mislabeled as expected return.
- [ ] Decision provenance can be linked to later realized outcomes without mutating the decision-time snapshot.
- [ ] Existing point-in-time / leakage defenses remain intact.
- [ ] Required regression evidence is recorded.
- [ ] No unrelated feature expansion occurred.
- [ ] No commit/push/PR/merge/deploy was performed without separate owner authorization.
- [ ] Codex stops after the final report.

---

## FINAL OWNER CONTROL

This document defines the authorized implementation scope.

Anything not explicitly required above is **out of scope**.

When uncertain:

> **FAIL CLOSED → REPORT → DO NOT EXPAND SCOPE.**

---

# FINAL STATUS ADDENDUM — 2026-09-30

This addendum records the final disposition of the authorized project workflow
01–12. It supersedes earlier open, pending, or authorization-gated status
statements where they conflict with the final state below. The original work
order and its historical evidence remain preserved above.

## 1. Formal Workflow Closure

```text
01. P0-A — Market Date / Time Semantic Integrity
    PASS / CLOSED

02. P0-B — Futures Contract Multiplier / Execution Cost Integrity
    PASS / CLOSED

03. P0 Regression Gate
    PASS / CLOSED

04. P1-A — Portfolio VaR Correction
    PASS / CLOSED

05. P1-B — Portfolio Risk Contribution Correction
    PASS / CLOSED

06. P1-C — Sharpe / Return Metric Semantic Correction
    PASS / CLOSED

07. P1-D — Decision Provenance + Outcome Ledger
    PASS / CLOSED

08. P1 Regression Gate
    PASS / CLOSED

09. P2-A — Large-Module Technical-Debt Containment
    PASS / CLOSED

10. Package Hygiene Verification
    CLOSED

11. Full Authorized Regression Verification
    PASS / CLOSED
    PASS WITH ACCEPTED CONDITIONS

12. Final Report
    PASS / CLOSED

AUTHORIZED PROJECT WORKFLOW 01–12:
FORMALLY COMPLETE AND CLOSED
```

## 2. Final Main and Promotion History

Final accepted `main`:

`2db5ecf72d65dcf31e8bc5b7b6bef958a8c01a12`

P1-D promotion:

- Source commit: `2cc8486af863f0169cf145070d61f4a6018e7a11`
- PR: `#27`
- Merge: `c41349c56b8a3a8143e5af1818c272b41ea5ed9f`

P2-A promotion:

- Source branch: `p2a-final-containment-package-hygiene`
- Source commit: `377d3cac234b4f17d91a1b234c39a27b2cafae39`
- Commit message: `P2-A: contain package and CI hygiene debt`
- PR: `#28 — P2-A: finalize package and CI hygiene containment`
- Merge / final main: `2db5ecf72d65dcf31e8bc5b7b6bef958a8c01a12`
- Promoted files: the P1 quality, P2 provenance, and TD-03 workflows, plus
  `package.json` and `package-lock.json`
- Branch protection bypass: none
- Deployment: none

## 3. P0 Final State

```text
P0-A:
PASS / CLOSED

P0-B:
PASS / CLOSED

P0 Regression Gate:
PASS / CLOSED

P0:
PASS / CLOSED
```

Model A authoritative economics remain unchanged:

```text
gross:       4000
commission:   180
tax:          1.68
slippage:     800
total cost:   981.68
net:         3018.32
```

## 4. P1 Final State and Contracts

```text
P1-A:
PASS / CLOSED

P1-B:
PASS / CLOSED

P1-C:
PASS / CLOSED

P1-D:
PASS / CLOSED

P1 Regression Gate:
PASS / CLOSED

P1:
PASS / CLOSED
```

Preserved contracts and semantic conclusions:

- `P1D_DIRECTION_V1` and `P0B_FUTURES_COST_V1`
- Historical VaR / ES95 and covariance-aware Euler risk contribution
- Sharpe labels match the implemented metric semantics
- Decision-time provenance remains immutable and separate from the outcome ledger
- No inferred direction, look-ahead, fabricated missing data, or fake predictive confidence

## 5. P2-A and Package Hygiene

```text
P2-A FINAL CONTAINMENT:
PASS WITH DEFERRED NON-BLOCKERS / CLOSED

P2-A GIT PROMOTION:
PASS / CLOSED

P2-A:
PASS / CLOSED
```

P2-A completed without unjustified large-module decomposition. Its final
assessment was:

`NO LARGE-MODULE CODE CHANGE REQUIRED`

`builders.py` and `fetchers.py` remain structural-risk candidates; no current
correctness, reliability, repeated-regression, testability, roadmap, or release
blocker justified splitting them. This work did not eliminate that structural
debt.

Package Hygiene Verification is **CLOSED**. The promoted remediation:

- Aligned applicable CI Node jobs from Node 22 to `24.18.0`
- Added deterministic `npm ci` materialization to applicable Node jobs
- Made TD-03 install both `requirements.txt` and
  `regression/requirements-regression.txt`
- Updated Wrangler `4.79.0 -> 4.144.0`, remaining on major v4
- Kept Terser at `5.51.2`
- Produced post-remediation full and production npm audits with `0 vulnerabilities`

Python transitive locking remains:

`DEFER / NO CHANGE`

No demonstrated reproducibility failure justified introducing a new Python
lock-management architecture.

## 6. Full Authorized Regression Verification

```text
Full Authorized Regression Verification:
PASS / CLOSED

Classification:
PASS WITH ACCEPTED CONDITIONS
```

Recorded evidence includes:

- P0-A, P0-B, and P0-B1: PASS
- Quant/Q5 and point-in-time/no-lookahead: PASS
- P1-A: 12 checks; P1-B: 12 cases; P1-C: PASS; P1-D: 18 tests
- Cross-P1: PASS; derivatives platform: 206 tests
- Security: 16 checks; Python compile: 112 files; JavaScript syntax: 15 files
- E2E: PASS; offline verifier: 8 tests; TD02: 8 tests
- P2 provenance: 33 tests; interaction: 94 steps
- Runtime/loader: 21/21; negative stability: 7 cases
- Analytics wiring: PASS; quick baseline: `VERIFY_OK`

Final-main CI on `2db5ecf72d65dcf31e8bc5b7b6bef958a8c01a12`:

| Workflow | Run ID | Result |
|---|---:|---|
| P1 quality gate | `36659796931` | SUCCESS |
| P2 release provenance | `36659796954` | SUCCESS |
| TD-03 substitute validation | `36659797077` | SUCCESS |

The P2 `full-live-baseline` job was skipped by its workflow condition.

## 7. Residual Conditions / Known Non-Blocking Conditions

The following six conditions are retained for truthful final-state
documentation and monitoring. They do not mean the project is incomplete.

### 1. E1 visual difference

- Page: `derivatives-status.html`
- Status: `UNCHANGED ACCEPTED CONDITION` — PRE-EXISTING / DETERMINISTIC / NON-CAUSAL
- Diff: `13.8060%`
- Immediate remediation: `NOT REQUIRED`

```text
baseline:
1280×1537
75b931a9fe163ad799c8b232d46b0cf7acb5eb81ad61fcd22419e38bc8dcb12c

capture:
1280×1534
4435a5d61894aa9ae64fdc00d8876bb65c364f00c0a05ba7b580cf94f9ccd9df

mask:
c1d24069e7e35cc2c649709640b6c6b2106786f56808c2c73e22c6354d5bafad

differing pixels:
271613

bbox:
[0,44,1280,1537]
```

### 2. TWSE / live condition

- Status: `EXTERNAL / LOCAL ENVIRONMENT CONDITION`
- Observed: HTTP 502 on three live TWSE endpoints, `WinError 10013`, and outbound
  network restriction
- No application regression was established
- Immediate remediation: `NOT REQUIRED`

This is not a resolved production bug.

### 3. External font / network noise

- Status: `EXTERNAL CONDITION`
- External resources caused visual noise under the verification environment;
  no deterministic application/UI regression was established
- Immediate remediation: `NOT REQUIRED`

### 4. Raw full baseline

- Raw result remains `VERIFY_FAILED`
- Limited to the accepted E1 and external TWSE/live and font/network conditions
- Immediate remediation: `NOT REQUIRED`

The raw result is not GREEN and is not evidence that the project is incomplete.

### 5. `builders.py` / `fetchers.py` structural risk

- Status: `STRUCTURAL RISK EXISTS / NOT AN ACTIVE BLOCKER`
- No current correctness, reliability, repeated deterministic regression,
  testability, roadmap, or release blocker was established
- Conclusion: `NO LARGE-MODULE CODE CHANGE REQUIRED`
- Immediate remediation: `NOT REQUIRED`

Reassess only if concrete new evidence appears.

### 6. Python transitive locking

- Status: `DEFER / NO CHANGE`
- Direct dependencies remain pinned and current verification passed
- No transitive-resolution or reproducibility blocker was demonstrated
- Immediate remediation: `NOT REQUIRED`

Overall residual-condition disposition:

```text
RESIDUAL CONDITIONS:
KNOWN / ACCEPTED / NON-BLOCKING

IMMEDIATE REMEDIATION REQUIRED:
NO
```

Do not reopen P0, P1, P2-A, Package Hygiene Verification, or Full Authorized
Regression Verification solely because of these conditions.

## 8. Deployment and Delivery State

Owner decision:

```text
DEPLOYMENT:
DEFERRED DUE TO RENDER PLAN

DEPLOYMENT AUTHORIZATION:
NOT AUTHORIZED
```

Deployment is deferred due to Render plan / cost considerations. It is not a
failed code gate; the authorized project workflow is complete independently of
deployment.

This status documentation update does not authorize or perform Git promotion
or deployment:

```text
Additional implementation:
NONE

Additional commit:
NONE

Additional push:
NONE

Additional PR:
NONE

Additional merge:
NONE

Deployment:
NONE

Owner checkout:
UNTOUCHED
```

## 9. Final Formal Project State

```text
P0:
PASS / CLOSED

P1:
PASS / CLOSED

Package Hygiene Verification:
CLOSED

Full Authorized Regression Verification:
PASS / CLOSED
PASS WITH ACCEPTED CONDITIONS

P2-A:
PASS / CLOSED

Final Report:
PASS / CLOSED

AUTHORIZED PROJECT WORKFLOW 01–12:
FORMALLY COMPLETE AND CLOSED

RESIDUAL CONDITIONS:
KNOWN / ACCEPTED / NON-BLOCKING

IMMEDIATE REMEDIATION REQUIRED:
NO

DEPLOYMENT:
DEFERRED DUE TO RENDER PLAN
NOT AUTHORIZED
```
