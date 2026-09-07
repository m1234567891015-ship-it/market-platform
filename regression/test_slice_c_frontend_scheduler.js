"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const REPO_ROOT = require("node:path").resolve(__dirname, "..");
const flush = () => new Promise((resolve) => setImmediate(resolve));

function loadApi(fetchImpl = () => Promise.reject(new Error("unexpected fetch")), includeShared = false) {
  const source = [
    fs.readFileSync(require("node:path").join(REPO_ROOT, "js", "api.js"), "utf8"),
    includeShared ? fs.readFileSync(require("node:path").join(REPO_ROOT, "js", "render-shared.js"), "utf8") : "",
    "this.__scheduler = fetchWithTimeout.createRequestScheduler;",
    includeShared ? "this.__fetchDerivativesApi = fetchDerivativesApi;" : "",
  ].join("\n");
  const sandbox = {
    AbortController,
    clearTimeout,
    console,
    document: {
      createElement: () => ({ classList: { add() {} } }),
      querySelectorAll: () => [],
    },
    fetch: fetchImpl,
    setTimeout,
    window: { location: { pathname: "derivatives-analytics.html" } },
  };
  vm.runInNewContext(source, sandbox, { filename: includeShared ? "frontend-runtime.js" : "api.js" });
  return sandbox;
}

async function testConcurrencyLimitAndBurstCompletion() {
  const scheduler = loadApi().__scheduler(3);
  const releases = [];
  const started = [];
  let active = 0;
  let maxActive = 0;
  const tasks = Array.from({ length: 9 }, (_, index) => scheduler.schedule(
    () => new Promise((resolve) => {
      active += 1;
      maxActive = Math.max(maxActive, active);
      started.push(index);
      releases[index] = () => {
        active -= 1;
        resolve(index);
      };
    }),
    { priority: 1, dedupeKey: `GET /api/burst?index=${index}` },
  ));

  await flush();
  assert.equal(maxActive, 3);
  assert.deepEqual(started, [0, 1, 2]);
  for (let index = 0; index < tasks.length; index += 1) {
    releases[index]();
    await flush();
  }
  await Promise.all(tasks);
  assert.equal(active, 0);
  assert.equal(started.length, 9);
  console.log("SLICE_C_FRONTEND_BURST_OK");
}

async function testPriorityAndSlotRelease() {
  const scheduler = loadApi().__scheduler(1);
  const started = [];
  let releaseFirst;
  const first = scheduler.schedule(() => new Promise((resolve) => {
    started.push("first");
    releaseFirst = resolve;
  }), { priority: 1, dedupeKey: "GET /api/first" });
  await flush();

  const low = scheduler.schedule(() => {
    started.push("low");
    return Promise.resolve("low");
  }, { priority: 3, dedupeKey: "GET /api/low" });
  let releaseHigh;
  const high = scheduler.schedule(() => {
    started.push("high");
    return new Promise((resolve) => {
      releaseHigh = resolve;
    });
  }, { priority: 1, dedupeKey: "GET /api/high" });

  releaseFirst("first");
  await first;
  await flush();
  assert.deepEqual(started, ["first", "high"]);
  releaseHigh("high");
  await high;
  await low;
  assert.deepEqual(started, ["first", "high", "low"]);

  await assert.rejects(
    scheduler.schedule(() => Promise.reject(new Error("failure")), { priority: 1, dedupeKey: "GET /api/failure" }),
    /failure/,
  );
  let recovered = false;
  await scheduler.schedule(() => {
    recovered = true;
    return Promise.resolve();
  }, { priority: 1, dedupeKey: "GET /api/recovered" });
  assert.equal(recovered, true);

  await assert.rejects(
    scheduler.schedule(() => Promise.reject(Object.assign(new Error("TIMEOUT"), { code: "TIMEOUT" })), {
      priority: 1,
      dedupeKey: "GET /api/timeout",
    }),
    (error) => error.code === "TIMEOUT",
  );
  let afterTimeout = false;
  await scheduler.schedule(() => {
    afterTimeout = true;
    return Promise.resolve();
  }, { priority: 1, dedupeKey: "GET /api/after-timeout" });
  assert.equal(afterTimeout, true);
}

async function testAbortReleasesQueuedSlot() {
  const scheduler = loadApi().__scheduler(1);
  let releaseFirst;
  const first = scheduler.schedule(() => new Promise((resolve) => {
    releaseFirst = resolve;
  }), { priority: 1, dedupeKey: "GET /api/held" });
  await flush();

  const controller = new AbortController();
  const aborted = scheduler.schedule(() => Promise.resolve("must-not-run"), {
    priority: 1,
    signal: controller.signal,
    dedupeKey: "GET /api/aborted",
  });
  controller.abort();
  await assert.rejects(aborted, (error) => error.code === "CANCELLED");
  releaseFirst("released");
  await first;

  let ran = false;
  await scheduler.schedule(() => {
    ran = true;
    return Promise.resolve();
  }, { priority: 1, dedupeKey: "GET /api/after-abort" });
  assert.equal(ran, true);
}

async function testInFlightDedupCleanupAndQueryIdentity() {
  const scheduler = loadApi().__scheduler(3);
  let resolveShared;
  let sharedCalls = 0;
  const first = scheduler.schedule(() => {
    sharedCalls += 1;
    return new Promise((resolve) => {
      resolveShared = resolve;
    });
  }, { priority: 1, dedupeKey: "GET /api/options?underlying=TXO" });
  const duplicate = scheduler.schedule(() => {
    sharedCalls += 1;
    return Promise.resolve("duplicate");
  }, { priority: 1, dedupeKey: "GET /api/options?underlying=TXO" });
  assert.strictEqual(first, duplicate);
  await flush();
  resolveShared({ value: "shared" });
  assert.deepEqual(await Promise.all([first, duplicate]), [{ value: "shared" }, { value: "shared" }]);
  assert.equal(sharedCalls, 1);

  let rerunCalls = 0;
  await scheduler.schedule(() => {
    rerunCalls += 1;
    return Promise.reject(new Error("shared failure"));
  }, { priority: 1, dedupeKey: "GET /api/failure?key=same" }).catch(() => {});
  await scheduler.schedule(() => {
    rerunCalls += 1;
    return Promise.resolve("recovered");
  }, { priority: 1, dedupeKey: "GET /api/failure?key=same" });
  assert.equal(rerunCalls, 2);

  let queryCalls = 0;
  await Promise.all([
    scheduler.schedule(() => { queryCalls += 1; return Promise.resolve("TXO"); }, { dedupeKey: "GET /api/options?underlying=TXO" }),
    scheduler.schedule(() => { queryCalls += 1; return Promise.resolve("MXO"); }, { dedupeKey: "GET /api/options?underlying=MXO" }),
  ]);
  assert.equal(queryCalls, 2);
}

async function testNormalizedFetchDedupAndFailClosed() {
  let fetchCalls = 0;
  const fakeFetch = async () => {
    fetchCalls += 1;
    return {
      headers: { get: () => "application/json" },
      ok: false,
      status: 503,
      text: async () => JSON.stringify({ success: false, error: { code: "UPSTREAM_DOWN", message: "資料暫不可用" } }),
    };
  };
  const runtime = loadApi(fakeFetch, true);
  const scheduler = runtime.__scheduler(3);
  const request = (url) => runtime.__fetchDerivativesApi(
    url,
    1000,
    undefined,
    { scheduler, priority: 1, dedupeKey: `GET ${url}` },
  );
  const [first, duplicate] = await Promise.all([
    request("/api/institution?product=TX"),
    request("/api/institution?product=TX"),
  ]);
  assert.equal(fetchCalls, 1);
  assert.deepEqual(first, duplicate);
  assert.equal(first.data, null);
  assert.equal(first.errorCode, "SERVICE_UNAVAILABLE");

  const source = fs.readFileSync(require("node:path").join(REPO_ROOT, "js", "page-global-market-assethub.js"), "utf8");
  assert.equal((source.match(/fetchWithTimeout\.createRequestScheduler\(3\)/g) || []).length, 2);
  assert.match(source, /fetchWithTimeout\.scheduleJsonRequest/);
  assert.match(source, /loadDerivativesAssetHubPayloads\(\{ includePublicOptionChain: true, scheduler \}\)/);
  assert.match(source, /request\("\/api\/options\/chain\?underlying=TXO&source=auto", 45000, 1\)/);
  assert.match(source, /request\("\/api\/institution\?product=TX", 12000, 2\)/);
  assert.match(source, /request\("\/api\/news\?category=derivatives&symbol=%5EVIX&limit=6", 20000, 3\)/);
  assert.doesNotMatch(source, /fetch(?:WithTimeout|DerivativesApi)\(\s*["'`]https?:/);
}

Promise.resolve()
  .then(testConcurrencyLimitAndBurstCompletion)
  .then(testPriorityAndSlotRelease)
  .then(testAbortReleasesQueuedSlot)
  .then(testInFlightDedupCleanupAndQueryIdentity)
  .then(testNormalizedFetchDedupAndFailClosed)
  .then(() => console.log("SLICE_C_FRONTEND_SCHEDULER_OK"))
  .catch((error) => {
    console.error(error);
    process.exitCode = 1;
  });
