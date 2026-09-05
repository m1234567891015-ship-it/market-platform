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
