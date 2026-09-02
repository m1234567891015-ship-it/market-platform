const CACHE_VERSION = "market-pulse-swr-20260902-us-etf-detail-1";
const RUNTIME_CACHE = `${CACHE_VERSION}-runtime`;

// TD-09: stale-while-revalidate for static assets only. /api/* (live TWSE/
// TAIFEX/Yahoo market data) and cross-origin requests (Google Fonts, etc.)
// always bypass the cache and go straight to the network - this list is an
// allowlist by design (fails closed to network passthrough for anything not
// explicitly recognized as a static asset), not a denylist of /api/.
const CACHEABLE_STATIC_EXTENSIONS = [".html", ".js", ".css", ".svg", ".png", ".webmanifest"];

function isCacheableStaticRequest(request) {
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return false;
  if (url.pathname.startsWith("/api/")) return false;
  return CACHEABLE_STATIC_EXTENSIONS.some((ext) => url.pathname.endsWith(ext));
}

self.addEventListener("install", (event) => {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys.filter((key) => key !== RUNTIME_CACHE).map((key) => caches.delete(key)),
      ))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("message", (event) => {
  if (event.data?.type === "SKIP_WAITING") {
    self.skipWaiting();
  }
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  // Do not call respondWith() for anything we're not actively caching -
  // re-issuing a request via fetch() inside respondWith() is not equivalent
  // to leaving it alone (cross-origin font/CSS requests can fail with
  // net::ERR_FAILED when re-issued this way); returning without calling
  // respondWith() lets the browser handle the request exactly as if no
  // service worker were installed at all.
  if (request.method !== "GET" || !isCacheableStaticRequest(request)) {
    return;
  }

  event.respondWith(
    caches.open(RUNTIME_CACHE).then((cache) =>
      cache.match(request).then((cached) => {
        const revalidate = fetch(request)
          .then((response) => {
            if (response.ok) cache.put(request, response.clone());
            return response;
          })
          .catch(() => cached);
        return cached || revalidate;
      }),
    ),
  );
});
