async function fetchWithTimeout(url, options = {}, timeoutMs = 8000) {
  const controller = new AbortController();
  const callerSignal = options.signal;
  let timedOut = false;
  const abortFromCaller = () => controller.abort();
  if (callerSignal) {
    if (callerSignal.aborted) abortFromCaller();
    else callerSignal.addEventListener("abort", abortFromCaller, { once: true });
  }
  const requestOptions = { ...options, signal: controller.signal };
  const timeoutHandler = () => {
    timedOut = true;
    controller.abort();
  };
  const timeoutId = setTimeout(timeoutHandler, timeoutMs);
  try {
    return await fetch(url, requestOptions);
  } catch (error) {
    if (controller.signal.aborted) {
      const controlledError = new Error(timedOut ? "TIMEOUT" : "CANCELLED");
      controlledError.code = timedOut ? "TIMEOUT" : "CANCELLED";
      controlledError.cause = error;
      throw controlledError;
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
    if (callerSignal) callerSignal.removeEventListener("abort", abortFromCaller);
  }
}

fetchWithTimeout.createRequestScheduler = function createFrontendRequestScheduler(limit = 3) {
  const maxConcurrent = Math.max(1, Number.isFinite(Number(limit)) ? Math.floor(Number(limit)) : 3);
  const queue = [];
  const inFlight = new Map();
  let active = 0;
  let sequence = 0;

  const cancelledError = () => {
    const error = new Error("CANCELLED");
    error.code = "CANCELLED";
    return error;
  };

  const removeQueuedTask = (task) => {
    const index = queue.indexOf(task);
    if (index >= 0) queue.splice(index, 1);
  };

  const cleanup = (task) => {
    if (task.signal && task.onAbort) task.signal.removeEventListener("abort", task.onAbort);
    if (task.dedupeKey && inFlight.get(task.dedupeKey) === task.promise) inFlight.delete(task.dedupeKey);
  };

  const pump = () => {
    while (active < maxConcurrent && queue.length) {
      queue.sort((left, right) => left.priority - right.priority || left.sequence - right.sequence);
      const task = queue.shift();
      if (task.settled) continue;
      if (task.signal?.aborted) {
        task.settled = true;
        cleanup(task);
        task.reject(cancelledError());
        continue;
      }
      task.started = true;
      active += 1;
      Promise.resolve()
        .then(() => task.run())
        .then(
          (value) => {
            if (task.settled) return;
            task.settled = true;
            cleanup(task);
            task.resolve(value);
          },
          (error) => {
            if (task.settled) return;
            task.settled = true;
            cleanup(task);
            task.reject(error);
          },
        )
        .then(() => {
          active -= 1;
          pump();
        });
    }
  };

  const schedule = (run, options = {}) => {
    if (typeof run !== "function") return Promise.reject(new TypeError("scheduled request must be a function"));
    const signal = options.signal;
    const dedupeKey = options.dedupeKey ? String(options.dedupeKey) : "";
    if (dedupeKey && inFlight.has(dedupeKey)) return inFlight.get(dedupeKey);
    if (signal?.aborted) return Promise.reject(cancelledError());

    let resolvePromise;
    let rejectPromise;
    const promise = new Promise((resolve, reject) => {
      resolvePromise = resolve;
      rejectPromise = reject;
    });
    const task = {
      run,
      signal,
      dedupeKey,
      priority: Number.isFinite(Number(options.priority)) ? Number(options.priority) : 1,
      sequence: sequence++,
      resolve: resolvePromise,
      reject: rejectPromise,
      promise,
      started: false,
      settled: false,
      onAbort: null,
    };
    if (dedupeKey) inFlight.set(dedupeKey, promise);
    if (signal) {
      task.onAbort = () => {
        if (task.started || task.settled) return;
        task.settled = true;
        removeQueuedTask(task);
        cleanup(task);
        task.reject(cancelledError());
        pump();
      };
      signal.addEventListener("abort", task.onAbort, { once: true });
    }
    queue.push(task);
    pump();
    return promise;
  };

  return {
    schedule,
    snapshot: () => ({ active, queued: queue.length, inFlight: inFlight.size }),
  };
};
