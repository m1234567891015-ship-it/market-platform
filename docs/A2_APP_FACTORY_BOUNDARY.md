# A2 app factory boundary

The first A2 slice introduces `app.create_app(config=None, derivatives_store=None)`.

- `app:app` remains the compatibility WSGI entrypoint used by Gunicorn and Render.
- The derivatives store is the first explicit application dependency.
- Factory-created applications bind their store at `app.extensions["derivatives_store"]`.
- Existing module-level `app.DERIVATIVES_STORE` access remains a compatibility fallback
  for legacy tests and deferred route imports.
- No route contract, provider fallback, background refresh policy, or deployment command
  changes in this slice.

The migration is intentionally incremental: later A2 slices may move additional
shared dependencies after equivalent boundary tests are in place.
