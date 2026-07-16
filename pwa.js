(() => {
  const VERSION = "20260703-no-forced-reload-1";
  const STORAGE_KEY = "market-pulse-static-version";

  async function unregisterServiceWorkers() {
    if (!("serviceWorker" in navigator)) return;
    const registrations = await navigator.serviceWorker.getRegistrations();
    await Promise.all(registrations.map((registration) => registration.unregister()));
  }

  async function clearBrowserCaches() {
    if (!("caches" in window)) return;
    const keys = await caches.keys();
    await Promise.all(keys.map((key) => caches.delete(key)));
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

  async function clearStaleRuntime() {
    const previousVersion = localStorage.getItem(STORAGE_KEY);
    if (previousVersion === VERSION) return;
    await Promise.all([unregisterServiceWorkers(), clearBrowserCaches()]);
    localStorage.setItem(STORAGE_KEY, VERSION);
  }

  document.addEventListener("DOMContentLoaded", () => {
    const controls = createControls();
    updateNetworkState(controls);
    window.addEventListener("online", () => updateNetworkState(controls));
    window.addEventListener("offline", () => updateNetworkState(controls));
    clearStaleRuntime()
      .catch((error) => console.warn(`PWA cache cleanup ${VERSION} failed`, error));
  });
})();
