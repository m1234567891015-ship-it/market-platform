type PagesEnv = {
  ORIGIN_API_BASE: string;
};

type PagesContext = {
  request: Request;
  env: PagesEnv;
};

const HOP_BY_HOP_HEADERS = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
  "host",
  "content-length",
  "forwarded",
  "x-forwarded-for",
  "x-forwarded-host",
  "x-forwarded-proto",
]);

const SECURITY_HEADERS: Record<string, string> = {
  "X-Content-Type-Options": "nosniff",
  "X-Frame-Options": "DENY",
  "Referrer-Policy": "strict-origin-when-cross-origin",
  "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
  "Content-Security-Policy":
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; manifest-src 'self'; worker-src 'self'; base-uri 'self'; frame-ancestors 'none'",
  "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
};

const API_CACHE_HEADERS: Record<string, string> = {
  "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
  Pragma: "no-cache",
  Expires: "0",
};

function buildUpstreamUrl(request: Request, originBase: string): URL {
  const base = new URL(originBase);
  if (!/^https?:$/.test(base.protocol) || base.username || base.password || base.hash) {
    throw new Error("ORIGIN_API_BASE must be an http(s) URL without credentials or fragments");
  }

  const incoming = new URL(request.url);
  const upstream = new URL(base.toString());
  upstream.pathname = incoming.pathname;
  upstream.search = incoming.search;
  return upstream;
}

function copyForwardableRequestHeaders(request: Request): Headers {
  const headers = new Headers();
  request.headers.forEach((value, name) => {
    if (!HOP_BY_HOP_HEADERS.has(name.toLowerCase())) headers.set(name, value);
  });
  return headers;
}

function copyResponseHeaders(response: Response): Headers {
  const headers = new Headers();
  response.headers.forEach((value, name) => {
    if (!HOP_BY_HOP_HEADERS.has(name.toLowerCase())) headers.set(name, value);
  });
  return headers;
}

function withHeaders(response: Response, extra: Record<string, string>): Response {
  const headers = copyResponseHeaders(response);
  Object.entries(extra).forEach(([name, value]) => headers.set(name, value));
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

function requestContext(request: Request): Record<string, unknown> {
  const url = new URL(request.url);
  return {
    path: url.pathname,
    method: request.method,
    parameter_names: Array.from(url.searchParams.keys()).sort(),
  };
}

function errorResponse(request: Request, code: string, message: string, status = 502): Response {
  return new Response(JSON.stringify({
    success: false,
    error_code: code,
    error: { code, message },
    request_context: requestContext(request),
  }), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      ...SECURITY_HEADERS,
      ...API_CACHE_HEADERS,
    },
  });
}

async function proxyApi(request: Request, env: PagesEnv): Promise<Response> {
  let upstreamUrl: URL;
  try {
    upstreamUrl = buildUpstreamUrl(request, env.ORIGIN_API_BASE);
  } catch (_error) {
    return errorResponse(request, "UPSTREAM_NOT_CONFIGURED", "API 上游尚未設定", 502);
  }

  const init: RequestInit = {
    method: request.method,
    headers: copyForwardableRequestHeaders(request),
    redirect: "manual",
  };
  if (request.method !== "GET" && request.method !== "HEAD") init.body = request.body;

  try {
    const upstreamResponse = await fetch(upstreamUrl, init);
    const contentType = upstreamResponse.headers.get("content-type") || "";
    if (upstreamResponse.status >= 200 && upstreamResponse.status < 300 && contentType.toLowerCase().includes("application/json")) {
      const body = await upstreamResponse.clone().text();
      if (!body.trim()) return errorResponse(request, "UPSTREAM_INVALID_RESPONSE", "API 上游回應為空", 502);
      try {
        JSON.parse(body);
      } catch (_error) {
        return errorResponse(request, "UPSTREAM_INVALID_RESPONSE", "API 上游回應格式錯誤", 502);
      }
    }
    return withHeaders(upstreamResponse, {
      ...SECURITY_HEADERS,
      ...API_CACHE_HEADERS,
    });
  } catch (_error) {
    return errorResponse(request, "UPSTREAM_UNAVAILABLE", "API 上游暫時無法使用", 502);
  }
}

// Static requests never enter this handler because _routes.json scopes
// Functions to /api/* only.
export async function onRequest(context: PagesContext): Promise<Response> {
  return proxyApi(context.request, context.env);
}
