# P4-01 Formal Acceptance / Closure

**Node:** P4-01 — Builders / Fetchers Domain
**Status:** CLOSED
**Result:** PASS — ENGINEERING / GOVERNANCE CLOSURE
**Formal closure:** Approved by Project Owner
**Closure date:** 2026-10-03

## A. Owner Decision and Contract Identity

Project Owner explicitly authorized P4-01 formal acceptance and closure. The accepted contract is `P4_01_BUILDERS_FETCHERS_DOMAIN_V1` in `docs/P4_01_BUILDERS_FETCHERS_DOMAIN_CONTRACT.md`. Its SHA-256 was verified at closure as:

```text
e6cded902fb3dff14404d5d688edd1f8c423cdddad425c8f42873f2c624bae6f
```

The contract bytes match the expected digest. No implementation redesign or later Phase 4 work was authorized.

## B. Accepted Finding and Remediation

The accepted pre-remediation finding was 13 direct generic transport/request operations across eight builders. The most direct boundary violation was Barchart cookie/XSRF request construction in the builder using a live opener returned by a fetcher.

The accepted remediation places provider retrieval behind named fetchers:

- Barchart cookie, XSRF, request, and option-contract normalization remain inside `fetchers.fetch_barchart_futures_options_payload`.
- Deribit and Bybit retrieval and provider-contract normalization use named fetchers.
- TWSE and TPEx requests use named payload adapters; latest-dataset retrieval uses named TWSE adapters.
- Yahoo class quote-page retrieval uses a named fetcher.
- Builders continue to perform domain assembly, selection, expiration, cache, and cross-source composition.

The formal-acceptance source audit parsed `builders.py` and found zero calls to `fetch_json`, `fetch_text`, `Request`, `urlopen`, `build_opener`, or `_urlopen_with_ssl_fallback`. The required named fetcher functions remain present. The route/service paths continue through their builders; no direct route-to-provider transport bypass was found in the audited paths.

## C. Accepted Domain and Semantic Boundaries

Provider transport, provider response decoding, and provider-level contract normalization belong to fetchers. Domain assembly and established cache/composition behavior belong to builders. Reusable parsers remain in their existing parser layer where applicable.

The closure audit found no reintroduced provider-date fabrication. Existing source roles remain distinct, including `TAIFEX_PRIMARY`, `YAHOO_SUPPLEMENT`, `YAHOO_EXPLICIT`, `YAHOO_AUTO_FALLBACK`, and `UNKNOWN`; `YAHOO_SUPPLEMENT` remains distinct from `YAHOO_AUTO_FALLBACK`. Existing P1-01 market-date and P1/P2 provenance regression evidence remains applicable.

Malformed JSON propagates as a decode error; invalid contracts and numeric fields are rejected; empty/error responses remain empty or error results rather than valid market data. No shared error framework was introduced. Existing provider exception and builder fallback behavior is preserved.

No score, Decision, Outcome, probability, regime, transaction-cost, Net Expectancy, Model Drift, market-time, or trading-strategy semantics were changed. No authoritative Decision/Outcome database was opened or mutated during P4-01 closure; no schema change or live capture occurred.

## D. Accepted Regression and Determinism Evidence

These are accepted results from the prior P4-01 execution, not tests rerun during formal closure:

```text
Focused P4-01 and dependency regression: 47 PASS
Derivatives Platform regression: 206 PASS
In-memory Python syntax validation: 5 files PASS
git diff --check: PASS
```

The focused command was:

```powershell
python -B -m unittest regression.test_p401_builders_fetchers_domain regression.test_p2_backend_boundaries regression.test_fetch_registry_bom regression.test_data_source_contracts regression.test_p203_source_provenance regression.test_p1_01_data_quality_remediation
```

The derivatives command was:

```powershell
python -B -m unittest test_derivatives_platform
```

Determinism fixtures established repeatable Deribit and Bybit normalized outputs and repeatable Bybit builder domain output after excluding its intentional wall-clock timestamp. Fixtures also covered the transport boundary, Barchart cookie/XSRF containment, malformed provider data, invalid numerics, empty results, and provider failures. Formal closure rechecked the contract hash and current source boundary; the accepted tests were not rerun because implementation and regression source files were unchanged after the accepted execution.

## E. Non-Blocking Test Hygiene Item

The prior derivatives test run emitted a `ResourceWarning` for the deliberately constructed HTTP 401 fixture in `test_fetch_yahoo_quote_summary_retries_with_crumb_after_unauthorized`. It is accepted as a non-blocking test-hygiene item. The suite passed, and no leaked production resource or P4-01 correctness defect was demonstrated.

## F. Explicit Non-Claims and Downstream Boundary

No live-provider verification was required or performed for P4-01 closure. Fixture evidence is not represented as live provider evidence. This closure does not claim Phase 4 closure or authorize later Phase 4 work.

```text
P4-01: CLOSED
ENGINEERING: PASS
BUILDERS / FETCHERS DOMAIN: VERIFIED
DIRECT BUILDER TRANSPORT OWNERSHIP: REMOVED
KNOWN P4-01 CORRECTNESS DEFECT: NONE

P4-02+: NOT AUTHORIZED / NOT STARTED
PHASE 4 FORMAL CLOSURE: NOT AUTHORIZED
GIT PROMOTION: NOT AUTHORIZED
DEPLOYMENT: NOT AUTHORIZED
```
