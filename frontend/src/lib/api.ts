/**
 * lib/api.ts
 *
 * Browser-side API helper for the web frontend.
 *
 * Production-ready model (Client V0):
 * - All `/api/v1/*` calls go to the Next.js BFF proxy route handler at
 *   `src/app/api/v1/[...path]/route.ts`.
 * - Access/refresh tokens are stored as HttpOnly cookies by the BFF.
 * - The browser never handles refresh tokens directly.
 *
 * This module focuses on:
 * - attaching scope headers (X-Tenant-Id / X-Company-Id / X-Branch-Id),
 * - unwrapping the enterprise response envelope,
 * - surfacing stable error codes and correlation ids for support.
 */

export const API_BASE = ""; // Same-origin. BFF routes live under `/api/v1/*`.

type Persisted<T> = { state: T; version?: number };

type EnvelopeOk<T> = { ok: true; data: T; meta?: unknown };
type EnvelopeErr = {
  ok: false;
  error: { code: string; message: string; details?: unknown; correlation_id?: string };
};

export class ApiError extends Error {
  status: number;
  code: string;
  correlationId: string | null;
  details: unknown | null;
  method: string | null;
  endpoint: string | null;
  isNetworkError: boolean;

  constructor(opts: {
    status: number;
    message: string;
    code?: string | null;
    correlationId?: string | null;
    details?: unknown | null;
    method?: string | null;
    endpoint?: string | null;
    isNetworkError?: boolean;
  }) {
    super(opts.message);
    this.name = "ApiError";
    this.status = opts.status;
    this.code = opts.code ?? "unknown";
    this.correlationId = opts.correlationId ?? null;
    this.details = opts.details ?? null;
    this.method = opts.method ?? null;
    this.endpoint = opts.endpoint ?? null;
    this.isNetworkError = opts.isNetworkError ?? false;
  }
}

export function apiUrl(path: string): string {
  // Backend sometimes returns relative endpoints like "/api/v1/..."
  // Keep them same-origin so the Next.js BFF can proxy them.
  if (path.startsWith("http://") || path.startsWith("https://")) {
    // If the backend returns an absolute API URL, re-route it through the BFF.
    // This keeps auth cookie behavior consistent and avoids cross-origin failures.
    try {
      const u = new URL(path);
      if (u.pathname.startsWith("/api/v1/")) {
        return `${API_BASE}${u.pathname}${u.search}`;
      }
    } catch {
      // If parsing fails, fall back to the raw path.
    }
    return path;
  }
  if (!path.startsWith("/")) return `/${path}`;
  return `${API_BASE}${path}`;
}

function loadPersistedState<T>(key: string): T | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Persisted<T>;
    if (!parsed || typeof parsed !== "object") return null;
    return (parsed as Persisted<T>).state ?? null;
  } catch {
    return null;
  }
}

function scopeHeaders(): Record<string, string> {
  const sel = loadPersistedState<{
    tenantId?: string;
    companyId?: string;
    branchId?: string;
  }>("attendance-admin-selection");
  const headers: Record<string, string> = {};
  if (sel?.tenantId) headers["X-Tenant-Id"] = sel.tenantId;
  if (sel?.companyId) headers["X-Company-Id"] = sel.companyId;
  if (sel?.branchId) headers["X-Branch-Id"] = sel.branchId;
  return headers;
}

function redirectToLoginIfNeeded(): void {
  if (typeof window === "undefined") return;
  if (window.location.pathname === "/login") return;
  window.location.assign("/login");
}

function redirectToScopeIfNeeded(code: string, correlationId: string | null): void {
  if (typeof window === "undefined") return;
  if (window.location.pathname === "/scope") return;
  const url = new URL("/scope", window.location.origin);
  url.searchParams.set("reason", code);
  if (correlationId) url.searchParams.set("cid", correlationId);
  window.location.assign(url.toString());
}

function isScopeErrorCode(code: string): boolean {
  return (
    code === "iam.scope.tenant_required" ||
    code === "iam.scope.forbidden" ||
    code === "iam.scope.forbidden_tenant" ||
    code === "iam.scope.mismatch" ||
    code === "iam.scope.invalid_tenant" ||
    code === "iam.scope.invalid_company" ||
    code === "iam.scope.invalid_branch"
  );
}

const SCOPE_TENANT_COOKIE = "noor_scope_tenant_id";
const SCOPE_COMPANY_COOKIE = "noor_scope_company_id";
const SCOPE_BRANCH_COOKIE = "noor_scope_branch_id";

function cookieSecure(): boolean {
  if (typeof window === "undefined") return false;
  return window.location.protocol === "https:" || process.env.NODE_ENV === "production";
}

function deleteCookie(name: string): void {
  if (typeof document === "undefined") return;
  const secure = cookieSecure() ? "; Secure" : "";
  document.cookie = `${name}=; Path=/; Max-Age=0; SameSite=Lax${secure}`;
}

function clearSelectionForScopeError(code: string): void {
  /**
   * If the scope stored in localStorage drifts (e.g. old company/branch), the
   * backend will fail-closed with `iam.scope.forbidden` and even `/auth/me`
   * can become inaccessible (because it uses the same scope headers).
   *
   * To recover without forcing users to open devtools, we clear the invalid
   * selection bits before sending them to `/scope`.
   *
   * IMPORTANT:
   * - For `tenant_required`, we keep selection untouched.
   * - For forbidden tenant, we also clear the tenant id so the user can re-pick.
   */
  if (typeof window === "undefined") return;
  if (code === "iam.scope.tenant_required") return;

  // Keep the BFF cookie mirror aligned with the local selection reset.
  deleteCookie(SCOPE_COMPANY_COOKIE);
  deleteCookie(SCOPE_BRANCH_COOKIE);
  if (code === "iam.scope.forbidden_tenant" || code === "iam.scope.invalid_tenant") {
    deleteCookie(SCOPE_TENANT_COOKIE);
  }

  const key = "attendance-admin-selection";
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return;

    const parsed = JSON.parse(raw) as { state?: Record<string, unknown>; version?: number };
    if (!parsed || typeof parsed !== "object" || !parsed.state || typeof parsed.state !== "object") {
      return;
    }

    // Clear dependent scope selections first.
    delete parsed.state.companyId;
    delete parsed.state.branchId;
    delete parsed.state.cameraId;
    if (code === "iam.scope.forbidden_tenant" || code === "iam.scope.invalid_tenant") {
      delete parsed.state.tenantId;
    }

    window.localStorage.setItem(key, JSON.stringify(parsed));
  } catch {
    // Best-effort only.
  }
}

function correlationIdFrom(res: Response): string | null {
  return res.headers.get("x-correlation-id") ?? res.headers.get("x-trace-id");
}

function unwrapOkEnvelopeOrThrow<T>(
  raw: unknown,
  ctx: {
    status: number;
    correlationId: string | null;
    method: string;
    endpoint: string;
  }
): T {
  if (raw && typeof raw === "object" && "ok" in raw) {
    const env = raw as EnvelopeOk<T> | EnvelopeErr;
    if (env.ok === true) return env.data;
    const err = (env as EnvelopeErr).error;
    const code = String(err?.code ?? "unknown");
    const message = String(err?.message ?? "Request failed");
    const correlationId =
      (err?.correlation_id ? String(err.correlation_id) : null) ?? ctx.correlationId;
    const details = err?.details ?? null;

    // Some legacy endpoints could theoretically return 200 with ok:false.
    // We still treat it as a client-visible failure with a sensible status.
    const status = ctx.status >= 200 && ctx.status < 300 ? 400 : ctx.status;
    throw new ApiError({
      status,
      code,
      message,
      correlationId,
      details,
      method: ctx.method,
      endpoint: ctx.endpoint,
    });
  }

  return raw as T;
}

async function readError(
  res: Response,
  ctx: { method: string; endpoint: string }
): Promise<ApiError> {
  const correlationId = correlationIdFrom(res);

  const text = await res.text();
  try {
    const json = JSON.parse(text) as EnvelopeOk<unknown> | EnvelopeErr | Record<string, unknown>;
    if (json && typeof json === "object") {
      if ("ok" in json && (json as EnvelopeErr).ok === false && (json as EnvelopeErr).error) {
        const err = (json as EnvelopeErr).error;
        const code = String(err.code ?? "unknown");
        const message = String(err.message ?? "Request failed");
        const cid =
          (err.correlation_id ? String(err.correlation_id) : null) ??
          correlationId;
        const details = err.details ?? null;
        return new ApiError({
          status: res.status,
          code,
          message,
          correlationId: cid,
          details,
          method: ctx.method,
          endpoint: ctx.endpoint,
        });
      }
      if ("detail" in json) {
        const detail = (json as Record<string, unknown>).detail;
        const msg = typeof detail === "string" ? detail : JSON.stringify(detail);
        return new ApiError({
          status: res.status,
          code: "unknown",
          message: msg,
          correlationId,
          method: ctx.method,
          endpoint: ctx.endpoint,
        });
      }
    }
  } catch {
    // Not JSON.
  }

  return new ApiError({
    status: res.status,
    code: "unknown",
    message: text || `${res.status} ${res.statusText}`,
    correlationId,
    method: ctx.method,
    endpoint: ctx.endpoint,
  });
}

function maybeRedirectOnError(err: ApiError): void {
  if (err.status === 401) {
    redirectToLoginIfNeeded();
    return;
  }
  if (err.code && isScopeErrorCode(err.code)) {
    clearSelectionForScopeError(err.code);
    redirectToScopeIfNeeded(err.code, err.correlationId);
  }
}

export async function apiEnvelope<T>(
  path: string,
  init?: RequestInit
): Promise<{ data: T; meta?: unknown }> {
  /**
   * Envelope-aware API helper that preserves `meta` when returned.
   *
   * Prefer `apiJson<T>()` for most calls; use `apiEnvelope<T>()` only when the
   * backend includes pagination meta (e.g., /iam/users).
   */
  const method = String(init?.method ?? "GET").toUpperCase();
  const endpoint = path;

  let res: Response;
  try {
    res = await fetch(apiUrl(path), {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...scopeHeaders(),
        ...(init?.headers ?? {}),
      },
      cache: "no-store",
    });
  } catch (e) {
    throw new ApiError({
      status: 0,
      code: "network_error",
      message: e instanceof Error ? e.message : "Network error",
      correlationId: null,
      details: null,
      method,
      endpoint,
      isNetworkError: true,
    });
  }

  if (!res.ok) {
    const err = await readError(res, { method, endpoint });
    maybeRedirectOnError(err);
    throw err;
  }

  const raw = (await res.json()) as unknown;
  const correlationId = correlationIdFrom(res);

  if (raw && typeof raw === "object" && "ok" in raw) {
    const env = raw as EnvelopeOk<T> | EnvelopeErr;
    if (env.ok === true) {
      return {
        data: (env as EnvelopeOk<T>).data,
        meta: (env as EnvelopeOk<T>).meta,
      };
    }

    const err = (env as EnvelopeErr).error;
    const code = String(err?.code ?? "unknown");
    const message = String(err?.message ?? "Request failed");
    const cid =
      (err?.correlation_id ? String(err.correlation_id) : null) ??
      correlationId;
    const details = err?.details ?? null;

    const status = res.status >= 200 && res.status < 300 ? 400 : res.status;
    const apiErr = new ApiError({
      status,
      code,
      message,
      correlationId: cid,
      details,
      method,
      endpoint,
    });
    maybeRedirectOnError(apiErr);
    throw apiErr;
  }

  // Non-enveloped responses are treated as data-only (legacy-safe).
  return { data: raw as T };
}

export async function apiJson<T>(path: string, init?: RequestInit): Promise<T> {
  const method = String(init?.method ?? "GET").toUpperCase();
  const endpoint = path;

  let res: Response;
  try {
    res = await fetch(apiUrl(path), {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...scopeHeaders(),
        ...(init?.headers ?? {}),
      },
      cache: "no-store",
    });
  } catch (e) {
    throw new ApiError({
      status: 0,
      code: "network_error",
      message: e instanceof Error ? e.message : "Network error",
      correlationId: null,
      details: null,
      method,
      endpoint,
      isNetworkError: true,
    });
  }

  if (!res.ok) {
    const err = await readError(res, { method, endpoint });
    maybeRedirectOnError(err);
    throw err;
  }

  const raw = (await res.json()) as unknown;
  return unwrapOkEnvelopeOrThrow<T>(raw, {
    status: res.status,
    correlationId: correlationIdFrom(res),
    method,
    endpoint,
  });
}

export async function apiForm<T>(
  path: string,
  form: FormData,
  init?: RequestInit
): Promise<T> {
  const method = String(init?.method ?? "POST").toUpperCase();
  const endpoint = path;

  // IMPORTANT: don't set Content-Type for FormData; browser sets boundary.
  let res: Response;
  try {
    res = await fetch(apiUrl(path), {
      method: init?.method ?? "POST",
      ...init,
      body: form,
      headers: {
        ...scopeHeaders(),
        ...(init?.headers ?? {}),
      },
      cache: "no-store",
    });
  } catch (e) {
    throw new ApiError({
      status: 0,
      code: "network_error",
      message: e instanceof Error ? e.message : "Network error",
      correlationId: null,
      details: null,
      method,
      endpoint,
      isNetworkError: true,
    });
  }

  if (!res.ok) {
    const err = await readError(res, { method, endpoint });
    maybeRedirectOnError(err);
    throw err;
  }

  // Some endpoints might return JSON, some might return text; handle both.
  const text = await res.text();
  try {
    return unwrapOkEnvelopeOrThrow<T>(JSON.parse(text) as unknown, {
      status: res.status,
      correlationId: correlationIdFrom(res),
      method,
      endpoint,
    });
  } catch {
    return text as unknown as T;
  }
}

export function xhrUploadFormWithProgress<T>(
  path: string,
  form: FormData,
  onProgress: (pct: number) => void
): Promise<T> {
  /**
   * Used for large video uploads (so you can show % progress).
   * We use XHR because fetch() upload progress is not reliable across browsers.
   *
   * IMPORTANT:
   * - Requests go to the Next.js BFF proxy (same-origin), so HttpOnly cookies
   *   are sent automatically by the browser.
   */
  const url = apiUrl(path);

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", url);
    const method = "PUT";
    const endpoint = path;

    const scope = scopeHeaders();
    for (const [k, v] of Object.entries(scope)) {
      xhr.setRequestHeader(k, v);
    }

    xhr.upload.onprogress = (evt) => {
      if (!evt.lengthComputable) return;
      onProgress(Math.round((evt.loaded / evt.total) * 100));
    };

    xhr.onload = () => {
      const correlationId =
        xhr.getResponseHeader("x-correlation-id") ??
        xhr.getResponseHeader("x-trace-id");

      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(
            unwrapOkEnvelopeOrThrow<T>(JSON.parse(xhr.responseText) as unknown, {
              status: xhr.status,
              correlationId,
              method,
              endpoint,
            })
          );
        } catch {
          resolve(xhr.responseText as unknown as T);
        }
      } else if (xhr.status === 401) {
        redirectToLoginIfNeeded();
        reject(
          new ApiError({
            status: 401,
            code: "unauthorized",
            message: "Unauthorized",
            correlationId,
            method,
            endpoint,
          })
        );
      } else {
        // Try to parse a structured envelope error (preferred). Otherwise, fall back
        // to a raw message.
        try {
          const json = JSON.parse(xhr.responseText) as EnvelopeErr;
          if (json && typeof json === "object" && "ok" in json && json.ok === false && json.error) {
            const cid =
              (json.error.correlation_id ? String(json.error.correlation_id) : null) ??
              correlationId;
            const err = new ApiError({
              status: xhr.status,
              code: String(json.error.code ?? "unknown"),
              message: String(json.error.message ?? "Request failed"),
              correlationId: cid,
              details: json.error.details ?? null,
              method,
              endpoint,
            });
            maybeRedirectOnError(err);
            reject(err);
            return;
          }
        } catch {
          // ignore
        }

        const err = new ApiError({
          status: xhr.status,
          code: "unknown",
          message: xhr.responseText
            ? `Upload failed: ${xhr.status} ${xhr.responseText}`
            : `Upload failed: ${xhr.status}`,
          correlationId,
          method,
          endpoint,
        });
        maybeRedirectOnError(err);
        reject(err);
      }
    };

    xhr.onerror = () =>
      reject(
        new ApiError({
          status: 0,
          code: "network_error",
          message: "Upload network error",
          correlationId: null,
          details: null,
          method: "PUT",
          endpoint: path,
          isNetworkError: true,
        })
      );
    xhr.send(form);
  });
}

export function isJsonContentType(contentType: string | null): boolean {
  if (!contentType) return false;
  const ct = contentType.toLowerCase();
  return ct.includes("application/json") || ct.includes("+json");
}

export function parseContentDispositionFilename(header: string | null): string | null {
  /**
   * Parse the filename from a Content-Disposition header.
   *
   * Supports:
   * - filename="report.csv"
   * - filename*=UTF-8''report%20(1).csv
   */
  if (!header) return null;
  const parts = header.split(";").map((p) => p.trim());

  const filenameStar = parts.find((p) => p.toLowerCase().startsWith("filename*="));
  if (filenameStar) {
    const raw = filenameStar.split("=", 2)[1]?.trim() ?? "";
    const unquoted = raw.replace(/^"(.*)"$/, "$1");
    const idx = unquoted.indexOf("''");
    const encoded = idx >= 0 ? unquoted.slice(idx + 2) : unquoted;
    try {
      const decoded = decodeURIComponent(encoded);
      if (decoded) return decoded;
    } catch {
      if (encoded) return encoded;
    }
  }

  const filename = parts.find((p) => p.toLowerCase().startsWith("filename="));
  if (filename) {
    const raw = filename.split("=", 2)[1]?.trim() ?? "";
    const unquoted = raw.replace(/^"(.*)"$/, "$1");
    return unquoted || null;
  }

  return null;
}

export function saveBlobAsFile(blob: Blob, filename: string): void {
  /**
   * Minimal browser download helper (no external dependencies).
   *
   * Note: Some browsers require the <a> to be attached to the DOM.
   */
  if (typeof window === "undefined" || typeof document === "undefined") return;
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename || "download";
  a.rel = "noreferrer";
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}

function fallbackFilenameFromPath(path: string): string {
  const clean = path.split("?")[0]?.split("#")[0] ?? path;
  const parts = clean.split("/").filter(Boolean);
  const last = parts[parts.length - 1] ?? "download";
  // Avoid filenames like "download" for "/.../download".
  if (last.toLowerCase() === "download") return "download";
  return last;
}

export async function apiDownload(
  path: string,
  init?: RequestInit & { filename?: string }
): Promise<{ filename: string; blob: Blob; contentType: string | null }> {
  /**
   * Download helper for "raw bytes" endpoints (artifacts, snapshots, exports).
   *
   * Rules:
   * - Success responses are treated as bytes (we do NOT JSON-parse on success).
   * - Failure responses are parsed as an envelope error when possible.
   */
  const method = String(init?.method ?? "GET").toUpperCase();
  const endpoint = path;

  let res: Response;
  try {
    res = await fetch(apiUrl(path), {
      ...init,
      headers: {
        ...scopeHeaders(),
        ...(init?.headers ?? {}),
      },
      cache: "no-store",
    });
  } catch (e) {
    throw new ApiError({
      status: 0,
      code: "network_error",
      message: e instanceof Error ? e.message : "Network error",
      correlationId: null,
      details: null,
      method,
      endpoint,
      isNetworkError: true,
    });
  }

  if (!res.ok) {
    const err = await readError(res, { method, endpoint });
    maybeRedirectOnError(err);
    throw err;
  }

  const cd = res.headers.get("content-disposition");
  const ct = res.headers.get("content-type");
  const headerFilename = parseContentDispositionFilename(cd);
  const filename = init?.filename ?? headerFilename ?? fallbackFilenameFromPath(path);
  const blob = await res.blob();

  return { filename, blob, contentType: ct };
}
