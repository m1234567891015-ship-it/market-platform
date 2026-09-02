/* TD-02 full-site ESM loader with an explicit classic rollback path. */
(function () {
  const moduleSource = "market-pulse-esm.min.js?v=td02-full-esm-20260901-1";
  const commonFallback = "common-runtime.min.js?v=td18-minify-20260901-1";
  const routeFallback = "route-bundle.min.js?v=td18-minify-20260901-1";
  const statusFallback = "derivatives-status-addon.min.js?v=td18-minify-20260901-1";
  const ROLLBACK_STORAGE_KEY = "market-pulse-td02-esm-rollback";
  let fallbackStarted = false;

  function markState(value) {
    if (document.documentElement) document.documentElement.dataset.td02Esm = value;
  }

  function appendScript(src, onload) {
    const script = document.createElement("script");
    script.src = src;
    script.async = false;
    if (onload) script.onload = onload;
    document.head.appendChild(script);
  }

  function appendStatusFallback() {
    const originalAddEventListener = document.addEventListener;
    const deferredListeners = [];
    const restore = () => {
      if (document.addEventListener !== originalAddEventListener) {
        document.addEventListener = originalAddEventListener;
      }
      if (document.readyState !== "loading") deferredListeners.forEach((listener) => listener());
    };
    document.addEventListener = function (type, listener, options) {
      if (type !== "DOMContentLoaded") return originalAddEventListener.call(this, type, listener, options);
      let called = false;
      const callOnce = () => {
        if (called) return;
        called = true;
        listener.call(this);
      };
      deferredListeners.push(callOnce);
      if (document.readyState === "loading") originalAddEventListener.call(this, type, callOnce, options);
      else callOnce();
    };
    appendScript(statusFallback, restore);
  }

  function loadClassicFallback() {
    if (fallbackStarted) return;
    fallbackStarted = true;
    markState("classic-fallback");
    appendScript(commonFallback, () => {
      appendScript(routeFallback, () => {
        if (document.body?.dataset.page === "derivatives-status") appendStatusFallback();
      });
    });
  }

  const queryRollback = /(?:^|&)td02-esm=off(?:&|$)/.test(
    String(window.location.search || "").replace(/^\?/, "")
  );
  let storedRollback = false;
  try {
    storedRollback = window.sessionStorage.getItem(ROLLBACK_STORAGE_KEY) === "1";
    if (queryRollback) window.sessionStorage.setItem(ROLLBACK_STORAGE_KEY, "1");
  } catch {}
  const rollbackRequested = queryRollback || storedRollback;
  if (rollbackRequested) {
    loadClassicFallback();
    return;
  }

  const probe = document.createElement("script");
  if (!("noModule" in probe)) {
    loadClassicFallback();
    return;
  }
  markState("esm-loading");
  const moduleScript = document.createElement("script");
  moduleScript.type = "module";
  moduleScript.src = moduleSource;
  moduleScript.onerror = loadClassicFallback;
  moduleScript.onload = () => markState("esm-active");
  document.head.appendChild(moduleScript);
}());
