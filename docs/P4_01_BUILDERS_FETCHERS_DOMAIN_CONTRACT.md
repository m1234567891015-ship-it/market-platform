# P4-01 Builders / Fetchers Domain Contract

- **Contract ID:** `P4_01_BUILDERS_FETCHERS_DOMAIN_V1`
- **Status:** `FROZEN`
- **Authority:** Project Owner authorization for P4-01 Builders / Fetchers Domain execution.
- **Scope:** Minimum boundary contract for provider transport and provider-result handoff used by `builders.py`. It does not authorize a broad module split or later P4 work.

## 1. Domain ownership

- `fetchers.py` owns outbound provider transport: request construction, provider URL and parameters, headers, cookie/opener state, timeouts, response decoding, and provider-level response-envelope extraction.
- `parsers.py` owns reusable pure parsing where an existing parser boundary already exists.
- `builders.py` owns domain assembly, cross-provider composition, selection/fallback policy already assigned to its call path, cache behavior already assigned to the builder, and conversion of provider results into application responses.
- Builders may call named provider fetchers. They must not construct or send an HTTP request, own a provider opener/cookie session, or call generic transport primitives such as `fetch_json` / `fetch_text` directly.
- A provider fetcher may preserve a decoded provider JSON object when existing domain parsers consume that established shape. It must not expose HTTP response objects, openers, or transport state to a builder. Provider-specific normalized option contracts are returned as normalized records and source metadata.

## 2. Error and time semantics

- Existing exception, `None`, empty-result, and error-payload behavior is preserved at the existing consumer boundary. No new global provider-error vocabulary is introduced in P4-01.
- Provider market dates and source timestamps remain provider-derived or unavailable. No wall-clock value may substitute for a missing provider date.
- Transport failure, malformed response, or unrecognized schema must not be promoted to apparently valid domain data.

## 3. Provenance and compatibility

- Source roles continue to originate from actual provider execution and retain the established distinctions `TAIFEX_PRIMARY`, `YAHOO_SUPPLEMENT`, `YAHOO_EXPLICIT`, `YAHOO_AUTO_FALLBACK`, `CACHE`, and `UNKNOWN`.
- `YAHOO_SUPPLEMENT` remains distinct from `YAHOO_AUTO_FALLBACK`; instrument symbols alone do not establish provenance.
- Existing route, builder, fetcher, API, Decision, Outcome, P2, and P3 contracts remain compatible. Cache policy, response shape, scores, Decision eligibility, probability, Outcome, regime, and execution-cost behavior are outside the change surface.

## 4. P4-01 bounded audit/remediation surface

- Audit all transport-primitive call sites in `builders.py`; move provider request construction and execution behind named fetcher functions without changing public builder outputs.
- Complete the Barchart cookie-backed options request inside the fetcher boundary; no live opener or `Request` object crosses into a builder.
- Keep existing provider-to-domain composition in builders. Do not physically split large modules solely for style, duplicate parsers, change route ownership, or redesign the declarative registry.
- Preserve provider-specific date formats, request timeouts, URL parameters, response decoding, fallback order, logging/error behavior, and cache semantics.
- No authoritative Decision/Outcome database writes, schema changes, live provider verification requirement, Git promotion, or deployment.

## 5. Acceptance criteria

1. Relevant route/service paths are traced through builder and named fetcher to the provider boundary.
2. `builders.py` contains no executed HTTP request construction or generic transport-helper calls.
3. Provider request/response and cookie-session ownership is unambiguous in `fetchers.py`; provider parsing is not duplicated across layers for the migrated paths.
4. Invalid/empty/error responses retain fail-closed behavior and do not become valid market data.
5. Provider dates, source roles, fallback/supplement distinctions, and existing public payloads remain unchanged.
6. Focused regression covers the migrated fetcher/builder contract, failure cases, and a structural boundary guard; deterministic fixtures produce the same output for the same input.
7. Relevant P1-01 provenance/date, TAIFEX fetch-registry, builder, and backend-boundary regressions pass; modified Python files pass in-memory syntax validation; `git diff --check` passes.
8. The authoritative Decision/Outcome database remains untouched and no unrelated worktree change is overwritten.

## 6. Governance boundary

P4-01 execution PASS is not formal acceptance or closure. P4-02 and later nodes, Phase 4 formal closure, Git promotion, and deployment require separate Project Owner authorization.
