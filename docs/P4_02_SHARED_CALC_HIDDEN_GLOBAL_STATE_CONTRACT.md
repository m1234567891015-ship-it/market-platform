# P4-02 Shared-calc Hidden Global State Contract

- **Contract ID:** `P4_02_SHARED_CALC_EXPLICIT_INPUT_V1`
- **Status:** `FROZEN`
- **Authority:** Project Owner authorization `P4-02 — Shared-calc Remove Hidden Global State`.
- **Scope:** Remove hidden semantic ambient state from calculation logic in `js/shared-calc.js`, update sanctioned callers, and add focused structural, behavioral, replay, and determinism regressions. This is not a module decomposition.

## 1. Hidden semantic dependency

A dependency is semantic when changing it can change a calculation's trend, risk, regime, score, signal, recommendation, calculation result, backtest result, replay result, or Decision-support output while the declared function inputs remain unchanged.

Calculation logic in scope must not read mutable module globals, `window`, `globalThis`, ambient page data, hidden singleton state, or unrelated cache state for semantic inputs. Page/state adapters may read current application state only at the caller boundary and must pass the values explicitly.

## 2. Explicit-input contract

`buildInstitutionalBacktestFramework` receives an explicit `marketContext` containing the market fields consumed by its existing formula:

```text
marketInternationalIndexes
marketMacroFactors
marketVolatility
marketOverview
```

`analyzeTechnicalTheories` receives `marketContext` in its options object and passes it through to the institutional framework. Production page callers obtain this context from the existing `twEtfState.getMarketBreadthContext` state adapter. That adapter is the permitted ambient-state boundary; the calculation functions themselves do not resolve global `data`.

The function signature may retain an optional context to preserve established no-context behavior. Missing fields are treated using the existing market-factor availability rules: unavailable factors are omitted, the existing empty-layer fallback score remains 50, and coverage remains 0 when no market factors are available. There is no fallback to ambient/global data. Invalid numeric values remain unavailable under the existing `parseAnalysisNumber` behavior.

## 3. Point-in-time, replay, and backtest rules

- Callers pass the market context observed for that calculation; replay callers pass the replay-time context, never the latest page snapshot by implicit lookup.
- The same explicit historical fixture must produce the same result when unrelated current/global market state changes.
- Existing backtest inputs, chronology, execution timing, transaction costs, and output semantics remain unchanged.
- No Decision/Outcome provenance schema or database changes are included.

## 4. Cache and side-effect rules

- No cache is used by the affected institutional market-context calculation. No cache semantics are changed.
- The scoped calculation functions must not mutate semantic global or shared state.
- Stable module constants and UI/orchestrator state outside the calculation boundary are not defects solely because they are module-level.

## 5. Caller compatibility

All sanctioned `analyzeTechnicalTheories` page callers in `js/` pass both their existing explicit `marketBreadth` and the `marketContext` returned by the state adapter. Existing test callers use the same options shape. The existing output formula and API results are preserved for equivalent explicit input values.

## 6. Structural guard and determinism

A focused regression parses `js/shared-calc.js` with the repository's installed Acorn parser and identifies free references to prohibited ambient semantic globals in calculation functions. It separately verifies that the approved page/state adapter boundary and all sanctioned consumers wire `marketContext` explicitly. Behavioral tests prove that changing ambient `data` cannot change a result when explicit input is fixed, changing explicit semantic input can change the market layer, missing context does not fall back to ambient data, and repeated replay/backtest calculations are structurally deterministic.

## 7. Non-goals

- No formula, score, trend, risk, regime, portfolio, technical-indicator, probability, Decision, Outcome, transaction-cost, P2, or P3 semantic redesign.
- No UI redesign, framework, global store, module split, dead-code deletion, broad frontend migration, or P4-03/P4-04 work.
- No provider transport change, authoritative DB mutation, live-data requirement, Git promotion, or deployment.

## 8. Acceptance criteria

1. This contract remains frozen and its SHA-256 is recorded.
2. Every confirmed hidden semantic dependency in scoped calculation logic is removed or explicitly blocked with evidence.
3. The global-state adapter passes the existing market inputs explicitly; all sanctioned callers are updated.
4. Replay results are invariant to unrelated ambient current state; backtest calculations remain reproducible.
5. Missing explicit context cannot trigger an ambient/global fallback; existing missing-data output semantics are preserved and coverage remains observable.
6. The structural guard, explicit-input, missing-data, replay, backtest, determinism, and caller-compatibility tests pass.
7. No unintended business-formula change occurs; focused existing shared-calc and relevant P2/P3/P4-01 regressions pass.
8. Modified JavaScript parses; `git diff --check` passes.
9. The authoritative Decision/Outcome database remains untouched, P4-01 remains closed, and P4-03/P4-04 remain unstarted.
