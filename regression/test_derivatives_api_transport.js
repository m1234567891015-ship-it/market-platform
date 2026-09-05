const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

async function loadTimeoutHelper(fetchImpl) {
  const source = fs.readFileSync("js/api.js", "utf8") + "\nthis.__fetchWithTimeout = fetchWithTimeout;";
  const sandbox = {
    AbortController,
    clearTimeout,
    fetch: fetchImpl,
    setTimeout,
  };
  vm.runInNewContext(source, sandbox);
  return sandbox.__fetchWithTimeout;
}

async function testTimeoutAndAbort() {
  const rejectingFetch = (_url, options) => new Promise((_resolve, reject) => {
    if (options.signal.aborted) {
      reject(Object.assign(new Error("signal is aborted without reason"), { name: "AbortError" }));
      return;
    }
    options.signal.addEventListener("abort", () => reject(Object.assign(new Error("signal is aborted without reason"), { name: "AbortError" })), { once: true });
  });
  const fetchWithTimeout = await loadTimeoutHelper(rejectingFetch);
  await assert.rejects(fetchWithTimeout("/api/basis", {}, 15), (error) => error.code === "TIMEOUT" && error.message === "TIMEOUT");
  const caller = new AbortController();
  const cancelled = fetchWithTimeout("/api/basis", { signal: caller.signal }, 1000);
  setTimeout(() => caller.abort(), 15);
  await assert.rejects(cancelled, (error) => error.code === "CANCELLED" && error.message === "CANCELLED");
}

function testServiceWorkerApiBypass() {
  const handlers = {};
  const sandbox = {
    URL,
    caches: { keys: async () => [], open: async () => ({}) },
    self: {
      location: { origin: "https://market-pulse.test" },
      addEventListener: (type, handler) => { handlers[type] = handler; },
      clients: { claim: async () => {} },
      skipWaiting: async () => {},
    },
  };
  vm.runInNewContext(fs.readFileSync("service-worker.js", "utf8"), sandbox);
  let responded = false;
  handlers.fetch({
    request: { method: "GET", url: "https://market-pulse.test/api/basis?future=TX&spot=TAIEX" },
    respondWith: () => { responded = true; },
  });
  assert.equal(responded, false, "service worker intercepted an API request");
}

Promise.all([testTimeoutAndAbort(), testServiceWorkerApiBypass()])
  .then(() => console.log("DERIVATIVES_API_TRANSPORT_OK"))
  .catch((error) => { console.error(error); process.exitCode = 1; });
