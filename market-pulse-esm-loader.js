/* TD-02 full-site ESM loader with an explicit classic rollback path. */
(function () {
  const CURRENT_BUILD_VERSION = "td02-full-esm-609817ef86e1db46";
  const loaderUrl = document.currentScript?.src
    ? new URL(document.currentScript.src, document.baseURI)
    : null;
  const runtimeVersion = loaderUrl?.searchParams.get("v") || "unversioned";
  const moduleSource = `market-pulse-esm.min.js?v=${encodeURIComponent(runtimeVersion)}`;
  const RECOVERY_STORAGE_KEY = "market-pulse-runtime-recovery-attempted";
  const APP_SCOPE_PATH = "/";
  const APP_SERVICE_WORKER_PATH = "/service-worker.js";
  const APP_CACHE_PREFIX = "market-pulse-swr-";
  const commonFallback = "common-runtime.min.js?v=td18-minify-381f82f1f41aa0e0";
  const routeFallback = "route-bundle.min.js?v=td18-minify-381f82f1f41aa0e0";
  const statusFallback = "derivatives-status-addon.min.js?v=td18-minify-381f82f1f41aa0e0";
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

  function isAppWorker(worker) {
    if (!worker?.scriptURL) return false;
    try {
      const scriptUrl = new URL(worker.scriptURL, window.location.href);
      return scriptUrl.origin === window.location.origin && scriptUrl.pathname === APP_SERVICE_WORKER_PATH;
    } catch {
      return false;
    }
  }

  function isAppRegistration(registration) {
    if (!registration?.scope) return false;
    try {
      const scopeUrl = new URL(registration.scope, window.location.href);
      if (scopeUrl.origin !== window.location.origin || scopeUrl.pathname !== APP_SCOPE_PATH) return false;
      return [registration.active, registration.waiting, registration.installing].some(isAppWorker);
    } catch {
      return false;
    }
  }

  function hasRecoveryAttempted() {
    try {
      return window.sessionStorage.getItem(RECOVERY_STORAGE_KEY) === CURRENT_BUILD_VERSION;
    } catch {
      console.error("[Market Pulse] recovery loop guard unavailable; refusing reload");
      return true;
    }
  }

  function markRecoveryAttempted() {
    try {
      window.sessionStorage.setItem(RECOVERY_STORAGE_KEY, CURRENT_BUILD_VERSION);
      return true;
    } catch {
      console.error("[Market Pulse] recovery loop guard unavailable; refusing reload");
      return false;
    }
  }

  async function recoverLegacyRuntime() {
    if (!("serviceWorker" in navigator) || !("caches" in window)) {
      throw new Error("Service Worker or Cache Storage API unavailable");
    }
    const registrations = await navigator.serviceWorker.getRegistrations();
    const appRegistrations = registrations.filter(isAppRegistration);
    if (!appRegistrations.length && isAppWorker(navigator.serviceWorker.controller)) {
      throw new Error("application controller exists but its registration could not be identified");
    }
    await Promise.all(appRegistrations.map((registration) => registration.unregister()));
    const cacheKeys = await caches.keys();
    const appCacheKeys = cacheKeys.filter((key) => key.startsWith(APP_CACHE_PREFIX));
    await Promise.all(appCacheKeys.map((key) => caches.delete(key)));
    console.warn("[Market Pulse] legacy service worker recovery completed", {
      registrations: appRegistrations.length,
      caches: appCacheKeys.length,
    });
    const recoveryUrl = new URL(window.location.href);
    recoveryUrl.searchParams.set("runtime_recovery", CURRENT_BUILD_VERSION);
    window.location.replace(recoveryUrl.href);
  }

  function stripRecoveryQuery() {
    const currentUrl = new URL(window.location.href);
    if (currentUrl.searchParams.get("runtime_recovery") !== CURRENT_BUILD_VERSION) return;
    currentUrl.searchParams.delete("runtime_recovery");
    window.history.replaceState(null, "", `${currentUrl.pathname}${currentUrl.search}${currentUrl.hash}`);
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

  if (runtimeVersion !== CURRENT_BUILD_VERSION) {
    if (hasRecoveryAttempted()) {
      console.error("[Market Pulse] recovery already attempted; refusing reload loop", {
        requested: runtimeVersion,
        current: CURRENT_BUILD_VERSION,
      });
      return;
    }
    if (!markRecoveryAttempted()) return;
    console.warn("[Market Pulse] stale runtime generation detected", {
      requested: runtimeVersion,
      current: CURRENT_BUILD_VERSION,
    });
    console.warn("[Market Pulse] legacy service worker recovery started");
    recoverLegacyRuntime().catch((error) => {
      console.error("[Market Pulse] legacy service worker recovery failed; refusing reload", error);
    });
    return;
  }

  stripRecoveryQuery();

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
