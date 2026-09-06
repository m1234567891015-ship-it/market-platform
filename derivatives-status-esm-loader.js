(function () {
  const moduleSource = "derivatives-status-esm.js?v=td02-remain-02-20260901-1";
  const fallbackSource = "derivatives-status-addon.min.js?v=td18-minify-5e25eb24db6b5c9c";
  let fallbackStarted = false;

  function markState(value) {
    if (document.documentElement) {
      document.documentElement.dataset.td02Esm = value;
    }
  }

  function loadClassicFallback() {
    if (fallbackStarted) return;
    fallbackStarted = true;
    markState("classic-fallback");
    const fallback = document.createElement("script");
    fallback.src = fallbackSource;
    fallback.async = false;
    const originalAddEventListener = document.addEventListener;
    const fallbackListeners = [];
    const restoreAddEventListener = () => {
      if (document.addEventListener !== originalAddEventListener) {
        document.addEventListener = originalAddEventListener;
      }
      if (document.readyState !== "loading") {
        fallbackListeners.forEach((listener) => listener());
      }
    };
    document.addEventListener = function (type, listener, options) {
      if (type === "DOMContentLoaded") {
        let called = false;
        const callOnce = () => {
          if (called) return;
          called = true;
          listener.call(this);
        };
        fallbackListeners.push(callOnce);
        if (document.readyState !== "loading") {
          callOnce();
        } else {
          originalAddEventListener.call(this, type, callOnce, options);
        }
        return;
      }
      return originalAddEventListener.call(this, type, listener, options);
    };
    fallback.onload = restoreAddEventListener;
    fallback.onerror = restoreAddEventListener;
    document.head.appendChild(fallback);
  }

  const locationSearch = typeof window !== "undefined" && window.location
    ? window.location.search
    : "";
  const rollbackRequested = /(?:^|&)td02-esm=off(?:&|$)/.test(
    String(locationSearch || "").replace(/^\?/, "")
  );
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
