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
  code: string | null;
  correlationId: string | null;
  details: unknown | null;

  constructor(opts: {
    status: number;
    message: string;
    code?: string | null;
    correlationId?: string | null;
    details?: unknown | null;
  }) {
    super(opts.message);
    this.name = "ApiError";
    this.status = opts.status;
    this.code = opts.code ?? null;
    this.correlationId = opts.correlationId ?? null;
    this.details = opts.details ?? null;
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
    code === "iam.scope.mismatch"
  );
}

function unwrapOkEnvelope<T>(raw: unknown): T {
  if (raw && typeof raw === "object" && "ok" in raw) {
    const env = raw as EnvelopeOk<T> | EnvelopeErr;
    if (env.ok === true) return env.data;
    const err = (env as EnvelopeErr).error;
    if (err && typeof err === "object") {
      const code = String(err.code ?? "error");
      const message = String(err.message ?? "Request failed");
      const correlationId = err.correlation_id ? String(err.correlation_id) : null;
      const details = err.details ?? null;
      throw new ApiError({
        status: 400,
        code,
        message: `${code}: ${message}`,
        correlationId,
        details,
      });
    }
    throw new ApiError({ status: 400, code: "error", message: "Request failed" });
  }
  return raw as T;
}

async function readError(res: Response): Promise<ApiError> {
  const correlationId =
    res.headers.get("x-correlation-id") ?? res.headers.get("x-trace-id");

  const text = await res.text();
  try {
    const json = JSON.parse(text) as EnvelopeOk<unknown> | EnvelopeErr | Record<string, unknown>;
    if (json && typeof json === "object") {
      if ("ok" in json && (json as EnvelopeErr).ok === false && (json as EnvelopeErr).error) {
        const err = (json as EnvelopeErr).error;
        const code = String(err.code ?? "error");
        const message = String(err.message ?? "Request failed");
        const cid =
          (err.correlation_id ? String(err.correlation_id) : null) ??
          correlationId;
        const details = err.details ?? null;
        return new ApiError({
          status: res.status,
          code,
          message: `${code}: ${message}`,
          correlationId: cid,
          details,
        });
      }
      if ("detail" in json) {
        const detail = (json as Record<string, unknown>).detail;
        const msg = typeof detail === "string" ? detail : JSON.stringify(detail);
        return new ApiError({
          status: res.status,
          code: null,
          message: msg,
          correlationId,
        });
      }
    }
  } catch {
    // Not JSON.
  }

  return new ApiError({
    status: res.status,
    code: null,
    message: text || `${res.status} ${res.statusText}`,
    correlationId,
  });
}

function maybeRedirectOnError(err: ApiError): void {
  if (err.status === 401) {
    redirectToLoginIfNeeded();
    return;
  }
  if (err.code && isScopeErrorCode(err.code)) {
    redirectToScopeIfNeeded(err.code, err.correlationId);
  }
}

export async function apiJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(apiUrl(path), {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...scopeHeaders(),
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });

  if (!res.ok) {
    const err = await readError(res);
    maybeRedirectOnError(err);
    throw err;
  }

  const raw = (await res.json()) as unknown;
  return unwrapOkEnvelope<T>(raw);
}

export async function apiForm<T>(
  path: string,
  form: FormData,
  init?: RequestInit
): Promise<T> {
  // IMPORTANT: don't set Content-Type for FormData; browser sets boundary.
  const res = await fetch(apiUrl(path), {
    method: init?.method ?? "POST",
    ...init,
    body: form,
    headers: {
      ...scopeHeaders(),
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });

  if (!res.ok) {
    const err = await readError(res);
    maybeRedirectOnError(err);
    throw err;
  }

  // Some endpoints might return JSON, some might return text; handle both.
  const text = await res.text();
  try {
    return unwrapOkEnvelope<T>(JSON.parse(text) as unknown);
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

    const scope = scopeHeaders();
    for (const [k, v] of Object.entries(scope)) {
      xhr.setRequestHeader(k, v);
    }

    xhr.upload.onprogress = (evt) => {
      if (!evt.lengthComputable) return;
      onProgress(Math.round((evt.loaded / evt.total) * 100));
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(unwrapOkEnvelope<T>(JSON.parse(xhr.responseText) as unknown));
        } catch {
          resolve(xhr.responseText as unknown as T);
        }
      } else if (xhr.status === 401) {
        redirectToLoginIfNeeded();
        reject(new ApiError({ status: 401, message: "unauthorized" }));
      } else {
        reject(new Error(`Upload failed: ${xhr.status} ${xhr.responseText}`));
      }
    };

    xhr.onerror = () => reject(new Error("Upload network error"));
    xhr.send(form);
  });
}
