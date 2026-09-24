# A1 architecture decomposition evidence

## Slice 1: US-market search

The first A1 vertical slice is the `/api/us-market/search` flow.

`us_market_search.py` owns the search-specific composition boundary:

- local seed matching;
- listed-universe matching;
- independent NYSE and Yahoo search fan-in;
- response payload assembly.

`routes_global_market.py` remains the HTTP adapter and preserves the existing
route, response fields, provider fallback semantics, and concurrent source
fetch behavior. Provider fetch implementations remain in `fetchers.py` for
this slice so the extraction does not introduce unrelated import churn.

The existing route characterization test now patches the slice boundary,
while provider-specific tests remain against `fetchers.py`. This gives the
slice an independently testable route contract and leaves later provider
extraction as a separate A1 slice.
