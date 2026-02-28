/**
 * BFF proxy for `/api/v1/*`.
 *
 * Why:
 * - Browser should not store refresh tokens (XSS risk).
 * - Next.js (server) holds access/refresh tokens in HttpOnly cookies.
 * - This route proxies requests to the FastAPI backend and handles refresh rotation
 *   on 401 responses (once per request).
 *
 * Notes:
 * - We intentionally keep this "dumb proxy" for non-auth endpoints: it forwards
 *   method, query string, body, and scope headers (X-Tenant-Id, X-Company-Id,
 *   X-Branch-Id). Backend remains the source of truth for scoping.
 * - For `/api/v1/auth/*`, we set/clear cookies and redact tokens from responses.
 */

import { NextResponse, type NextRequest } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const ACCESS_COOKIE = "noor_access_token";
const REFRESH_COOKIE = "noor_refresh_token";

const SCOPE_TENANT_COOKIE = "noor_scope_tenant_id";
const SCOPE_COMPANY_COOKIE = "noor_scope_company_id";
const SCOPE_BRANCH_COOKIE = "noor_scope_branch_id";

type EnvelopeOk<T> = { ok: true; data: T; meta?: unknown };
type EnvelopeErr = {
  ok: false;
  error: {
    code: string;
    message: string;
    details?: unknown;
    correlation_id?: string;
  };
};

type TokenResponse = {
  access_token: string;
  refresh_token: string;
  user: unknown;
  roles: string[];
  permissions?: string[];
  scope: unknown;
};

function backendBaseUrl(): string {
  // Prefer a server-only internal URL when running inside Docker/K8s.
  // This value is not secret, but it should not be required by the browser.
  return (
    process.env.API_PROXY_TARGET ??
    process.env.BACKEND_API_BASE_URL ??
    process.env.NEXT_PUBLIC_API_BASE_URL ??
    "http://localhost:8000"
  );
}

function cookieSecure(): boolean {
  return process.env.NODE_ENV === "production";
}

function setAuthCookies(res: NextResponse, tokens: TokenResponse): void {
  // Access token is short-lived; refresh token is long-lived and must remain HttpOnly.
  res.cookies.set(ACCESS_COOKIE, tokens.access_token, {
    httpOnly: true,
    secure: cookieSecure(),
    sameSite: "lax",
    path: "/",
  });
  res.cookies.set(REFRESH_COOKIE, tokens.refresh_token, {
    httpOnly: true,
    secure: cookieSecure(),
    sameSite: "lax",
    path: "/",
  });
}

function clearAuthCookies(res: NextResponse): void {
  // Use delete() to emit Set-Cookie with Max-Age=0.
  res.cookies.delete(ACCESS_COOKIE);
  res.cookies.delete(REFRESH_COOKIE);
}

function passthroughHeaders(backendRes: Response): Headers {
  // We avoid proxying hop-by-hop headers. For our usage, a simple blacklist is
  // sufficient and keeps content-type/disposition/correlation headers intact.
  const headers = new Headers();
  for (const [k, v] of backendRes.headers.entries()) {
    const key = k.toLowerCase();
    if (key === "set-cookie") continue;
    // If we rewrite or re-stream the body (e.g. auth endpoints), these can
    // easily become invalid and cause the browser to reject the response.
    if (key === "content-length") continue;
    if (key === "content-encoding") continue;
    if (key === "connection") continue;
    if (key === "keep-alive") continue;
    if (key === "transfer-encoding") continue;
    if (key === "proxy-authenticate") continue;
    if (key === "proxy-authorization") continue;
    if (key === "te") continue;
    if (key === "trailer") continue;
    if (key === "upgrade") continue;
    headers.set(k, v);
  }
  return headers;
}

function isBranchScopedPath(path: string): boolean {
  // The backend treats branch_id/company_id/tenant_id path params as authoritative
  // and will inject matching scope headers server-side. Avoid injecting branch/company
  // from cookies for branch-scoped APIs to prevent `iam.scope.mismatch` surprises.
  return path.startsWith("/api/v1/branches/");
}

function scopeHeadersFrom(req: NextRequest, path: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const name of ["x-tenant-id", "x-company-id", "x-branch-id"]) {
    const v = req.headers.get(name);
    if (v) out[name] = v;
  }

  // Cookie fallback for requests that cannot attach headers (e.g. <img>, <a download>, new tab).
  if (!out["x-tenant-id"]) {
    const v = req.cookies.get(SCOPE_TENANT_COOKIE)?.value;
    if (v) out["x-tenant-id"] = v;
  }

  if (isBranchScopedPath(path)) {
    // Let backend infer company/branch from the path params.
    return out;
  }

  if (!out["x-company-id"]) {
    const v = req.cookies.get(SCOPE_COMPANY_COOKIE)?.value;
    if (v) out["x-company-id"] = v;
  }
  if (!out["x-branch-id"]) {
    const v = req.cookies.get(SCOPE_BRANCH_COOKIE)?.value;
    if (v) out["x-branch-id"] = v;
  }
  return out;
}

function accessTokenFrom(req: NextRequest): string | null {
  return req.cookies.get(ACCESS_COOKIE)?.value ?? null;
}

function refreshTokenFrom(req: NextRequest): string | null {
  return req.cookies.get(REFRESH_COOKIE)?.value ?? null;
}

async function proxyToBackend(
  req: NextRequest,
  opts: { path: string; withAuth: boolean; retryOn401: boolean },
): Promise<{
  backendRes: Response;
  rotatedTokens: { access_token: string; refresh_token: string } | null;
}> {
  const targetUrl = new URL(opts.path, backendBaseUrl());
  targetUrl.search = req.nextUrl.search;

  const headers: Record<string, string> = {
    ...scopeHeadersFrom(req, opts.path),
  };

  const contentType = req.headers.get("content-type");
  if (contentType) headers["content-type"] = contentType;
  const isJson = (contentType ?? "").toLowerCase().includes("application/json");

  const accept = req.headers.get("accept");
  if (accept) headers["accept"] = accept;

  // Correlation-id can be generated server-side in FastAPI middleware; if the
  // client sends one (e.g. for support), forward it.
  const cid =
    req.headers.get("x-correlation-id") ?? req.headers.get("x-trace-id");
  if (cid) headers["x-correlation-id"] = cid;

  if (opts.withAuth) {
    const at = accessTokenFrom(req);
    if (at) headers["authorization"] = `Bearer ${at}`;
  }

  // Stream body when present (important for uploads). Node fetch requires
  // `duplex: "half"` for streaming request bodies.
  const hasBody = !["GET", "HEAD"].includes(req.method.toUpperCase());
  // We can safely retry only if the request is body-less OR body is buffered.
  // For uploads (multipart/form-data), retrying would require buffering huge bodies,
  // so we refresh the session but ask the client to retry manually.
  const canRetry = !hasBody || isJson;

  let bufferedBody: ArrayBuffer | null = null;
  if (hasBody && isJson) {
    bufferedBody = await req.arrayBuffer();
  }
  const init: RequestInit & { duplex?: "half" } = {
    method: req.method,
    headers,
    cache: "no-store",
  };
  if (hasBody) {
    if (bufferedBody) {
      init.body = bufferedBody;
    } else {
      init.body = req.body;
      init.duplex = "half";
    }
  }

  let backendRes = await fetch(targetUrl.toString(), init);
  let rotatedTokens: { access_token: string; refresh_token: string } | null =
    null;

  if (backendRes.status === 401 && opts.retryOn401) {
    rotatedTokens = await refreshOnce(req);
    if (rotatedTokens) {
      if (canRetry) {
        // Re-issue the request using the rotated access token.
        const newAt = rotatedTokens.access_token;
        const retryHeaders = { ...headers, authorization: `Bearer ${newAt}` };
        const retryInit: RequestInit & { duplex?: "half" } = {
          ...init,
          headers: retryHeaders,
        };
        if (bufferedBody) retryInit.body = bufferedBody;
        backendRes = await fetch(targetUrl.toString(), retryInit);
      } else {
        // Session refreshed, but the request body is not safely replayable (e.g. upload).
        // Ask the client to retry manually; do NOT clear cookies.
        backendRes = new Response(
          JSON.stringify({
            ok: false,
            error: {
              code: "unauthorized_retryable",
              message: "Session refreshed; please retry the request",
            },
          }),
          { status: 409, headers: { "content-type": "application/json" } },
        );
      }
    }
  }

  return { backendRes, rotatedTokens };
}

async function readJson<T>(res: Response): Promise<T | null> {
  const ct = res.headers.get("content-type") ?? "";
  if (!ct.toLowerCase().includes("application/json")) return null;
  try {
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

async function refreshOnce(
  req: NextRequest,
): Promise<{ access_token: string; refresh_token: string } | null> {
  const rt = refreshTokenFrom(req);
  if (!rt) return null;

  const res = await fetch(
    new URL("/api/v1/auth/refresh", backendBaseUrl()).toString(),
    {
      method: "POST",
      headers: {
        "content-type": "application/json",
        ...scopeHeadersFrom(req, "/api/v1/auth/refresh"),
      },
      body: JSON.stringify({ refresh_token: rt }),
      cache: "no-store",
    },
  );
  if (!res.ok) return null;

  const raw = await readJson<EnvelopeOk<TokenResponse> | EnvelopeErr>(res);
  if (!raw || raw.ok !== true) return null;

  const data = (raw as EnvelopeOk<TokenResponse>).data;
  if (!data?.access_token || !data?.refresh_token) return null;

  return { access_token: data.access_token, refresh_token: data.refresh_token };
}

async function handleAuthLogin(req: NextRequest): Promise<NextResponse> {
  const { backendRes } = await proxyToBackend(req, {
    path: "/api/v1/auth/login",
    withAuth: false,
    retryOn401: false,
  });

  const headers = passthroughHeaders(backendRes);
  const raw = await readJson<EnvelopeOk<TokenResponse> | EnvelopeErr>(
    backendRes,
  );
  if (!raw) {
    return new NextResponse(backendRes.body, {
      status: backendRes.status,
      headers,
    });
  }

  if (raw.ok !== true) {
    return NextResponse.json(raw, { status: backendRes.status, headers });
  }

  const tokens = (raw as EnvelopeOk<TokenResponse>).data;
  const session = {
    user: tokens.user,
    roles: tokens.roles ?? [],
    permissions: tokens.permissions ?? [],
    scope: tokens.scope,
  };

  const res = NextResponse.json(
    { ok: true, data: session },
    { status: 200, headers },
  );
  setAuthCookies(res, tokens);
  return res;
}

async function handleAuthRefresh(req: NextRequest): Promise<NextResponse> {
  const rt = refreshTokenFrom(req);
  if (!rt) {
    // Treat as unauthenticated.
    const res = NextResponse.json(
      {
        ok: false,
        error: { code: "unauthorized", message: "Missing refresh token" },
      },
      { status: 401 },
    );
    clearAuthCookies(res);
    return res;
  }

  const backendRes = await fetch(
    new URL("/api/v1/auth/refresh", backendBaseUrl()).toString(),
    {
      method: "POST",
      headers: {
        "content-type": "application/json",
        ...scopeHeadersFrom(req, "/api/v1/auth/refresh"),
      },
      body: JSON.stringify({ refresh_token: rt }),
      cache: "no-store",
    },
  );

  const headers = passthroughHeaders(backendRes);
  const raw = await readJson<EnvelopeOk<TokenResponse> | EnvelopeErr>(
    backendRes,
  );
  if (!raw) {
    return new NextResponse(backendRes.body, {
      status: backendRes.status,
      headers,
    });
  }
  if (raw.ok !== true) {
    const res = NextResponse.json(raw, { status: backendRes.status, headers });
    // Refresh failure means the session is gone; clear cookies.
    clearAuthCookies(res);
    return res;
  }

  const tokens = (raw as EnvelopeOk<TokenResponse>).data;
  const session = {
    user: tokens.user,
    roles: tokens.roles ?? [],
    permissions: tokens.permissions ?? [],
    scope: tokens.scope,
  };

  const res = NextResponse.json(
    { ok: true, data: session },
    { status: 200, headers },
  );
  setAuthCookies(res, tokens);
  return res;
}

async function handleAuthLogout(req: NextRequest): Promise<NextResponse> {
  const rt = refreshTokenFrom(req);
  if (rt) {
    // Best-effort backend revocation; logout is idempotent on the backend.
    await fetch(new URL("/api/v1/auth/logout", backendBaseUrl()).toString(), {
      method: "POST",
      headers: {
        "content-type": "application/json",
        ...scopeHeadersFrom(req, "/api/v1/auth/logout"),
      },
      body: JSON.stringify({ refresh_token: rt }),
      cache: "no-store",
    }).catch(() => {
      // Ignore network errors on logout; we still clear local cookies.
    });
  }

  const res = NextResponse.json(
    { ok: true, data: { revoked: true } },
    { status: 200 },
  );
  clearAuthCookies(res);
  return res;
}

async function handleBootstrap(req: NextRequest): Promise<NextResponse> {
  // Dev-only bootstrap returns a TokenResponse. Treat it like login for cookies.
  const { backendRes } = await proxyToBackend(req, {
    path: "/api/v1/bootstrap",
    withAuth: false,
    retryOn401: false,
  });

  const headers = passthroughHeaders(backendRes);
  const raw = await readJson<EnvelopeOk<TokenResponse> | EnvelopeErr>(
    backendRes,
  );
  if (!raw) {
    return new NextResponse(backendRes.body, {
      status: backendRes.status,
      headers,
    });
  }
  if (raw.ok !== true) {
    return NextResponse.json(raw, { status: backendRes.status, headers });
  }

  const tokens = (raw as EnvelopeOk<TokenResponse>).data;
  const session = {
    user: tokens.user,
    roles: tokens.roles ?? [],
    permissions: tokens.permissions ?? [],
    scope: tokens.scope,
  };

  const res = NextResponse.json(
    { ok: true, data: session },
    { status: 200, headers },
  );
  setAuthCookies(res, tokens);
  return res;
}

type RouteContext = { params: Promise<{ path: string[] }> };

async function handle(req: NextRequest, ctx: RouteContext): Promise<Response> {
  // Next.js route handlers provide params asynchronously.
  const { path } = await ctx.params;
  const joined = path.join("/");
  const fullPath = `/api/v1/${joined}`;

  // Auth endpoints have special cookie behavior.
  if (fullPath === "/api/v1/auth/login") return handleAuthLogin(req);
  if (fullPath === "/api/v1/auth/refresh") return handleAuthRefresh(req);
  if (fullPath === "/api/v1/auth/logout") return handleAuthLogout(req);
  if (fullPath === "/api/v1/bootstrap") return handleBootstrap(req);

  const { backendRes, rotatedTokens } = await proxyToBackend(req, {
    path: fullPath,
    withAuth: true,
    retryOn401: true,
  });

  const res = new NextResponse(backendRes.body, {
    status: backendRes.status,
    headers: passthroughHeaders(backendRes),
  });

  if (rotatedTokens) {
    // Keep browser cookies aligned to backend refresh rotation.
    res.cookies.set(ACCESS_COOKIE, rotatedTokens.access_token, {
      httpOnly: true,
      secure: cookieSecure(),
      sameSite: "lax",
      path: "/",
    });
    res.cookies.set(REFRESH_COOKIE, rotatedTokens.refresh_token, {
      httpOnly: true,
      secure: cookieSecure(),
      sameSite: "lax",
      path: "/",
    });
  } else if (backendRes.status === 401) {
    // If we couldn't refresh, clear cookies so the client is forced to re-auth.
    clearAuthCookies(res);
  }

  return res;
}

export async function GET(req: NextRequest, ctx: RouteContext) {
  return handle(req, ctx);
}
export async function POST(req: NextRequest, ctx: RouteContext) {
  return handle(req, ctx);
}
export async function PUT(req: NextRequest, ctx: RouteContext) {
  return handle(req, ctx);
}
export async function PATCH(req: NextRequest, ctx: RouteContext) {
  return handle(req, ctx);
}
export async function DELETE(req: NextRequest, ctx: RouteContext) {
  return handle(req, ctx);
}
