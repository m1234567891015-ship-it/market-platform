(() => {
  const VERSION = "td02-full-esm-0110e9f506bddd37";
  const STORAGE_KEY = "market-pulse-static-version";
  const SERVICE_WORKER_URL = "service-worker.js?v=td02-full-esm-0110e9f506bddd37";
  const APP_SCOPE_PATH = "/";
  const APP_SERVICE_WORKER_PATH = "/service-worker.js";
  const APP_CACHE_PREFIX = "market-pulse-swr-";

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

  async function unregisterServiceWorkers() {
    if (!("serviceWorker" in navigator)) return;
    const registrations = await navigator.serviceWorker.getRegistrations();
    await Promise.all(registrations.filter(isAppRegistration).map((registration) => registration.unregister()));
  }

  async function clearBrowserCaches() {
    if (!("caches" in window)) return;
    const keys = await caches.keys();
    await Promise.all(keys.filter((key) => key.startsWith(APP_CACHE_PREFIX)).map((key) => caches.delete(key)));
  }

  async function registerServiceWorker() {
    if (!("serviceWorker" in navigator)) return;
    try {
      await navigator.serviceWorker.register(SERVICE_WORKER_URL);
    } catch (error) {
      console.warn(`PWA service worker registration failed`, error);
    }
  }

  function createControls() {
    const controls = document.createElement("div");
    controls.className = "pwa-controls";
    controls.setAttribute("aria-live", "polite");
    controls.innerHTML = `
      <span class="pwa-network" title="同步連線">
        <i></i><span>同步連線</span>
      </span>
    `;
    document.body.appendChild(controls);
    return controls;
  }

  function updateNetworkState(controls) {
    const status = controls.querySelector(".pwa-network");
    const label = status?.querySelector("span");
    if (!status || !label) return;
    status.classList.toggle("is-offline", !navigator.onLine);
    label.textContent = navigator.onLine ? "同步連線" : "離線";
  }

  async function syncRuntimeVersion() {
    const previousVersion = localStorage.getItem(STORAGE_KEY);
    if (previousVersion === VERSION) {
      await registerServiceWorker();
      return;
    }
    // Version bumped: flush any service worker/cache state left over from
    // the previous version before registering the current one, so a bad
    // cached state from an earlier release can never persist across a
    // version change (this is the same flush this file has always done -
    // it's now followed by a registration instead of leaving the site with
    // no service worker at all).
    await Promise.all([unregisterServiceWorkers(), clearBrowserCaches()]);
    await registerServiceWorker();
    localStorage.setItem(STORAGE_KEY, VERSION);
  }

  function bootstrapPwa() {
    const controls = createControls();
    updateNetworkState(controls);
    window.addEventListener("online", () => updateNetworkState(controls));
    window.addEventListener("offline", () => updateNetworkState(controls));
    syncRuntimeVersion()
      .catch((error) => console.warn(`PWA runtime sync ${VERSION} failed`, error));
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", bootstrapPwa, { once: true });
  else bootstrapPwa();
})();
