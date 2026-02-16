/**
 * lib/api.ts
 *
 * A tiny backend client:
 * - apiJson(): JSON requests + consistent error handling
 * - apiForm(): multipart/form-data requests (faces upload)
 * - xhrUploadFormWithProgress(): PUT upload with progress (video upload)
 *
 * Notes about your FastAPI backend:
 * - JSON endpoints live under /api/v1/...
 * - Responses are usually wrapped: { ok: true, data: ... } (enterprise envelope).
 * - Video upload expects: PUT /branches/{branch_id}/videos/{video_id}/file with FormData field name "file"
 * - Face upload expects: POST /branches/{branch_id}/employees/{employee_id}/faces/register with FormData field name "file" (single)
 *   (for multiple images, call the endpoint multiple times)
 */

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
// TODO: MAKE this enterprise production ready for security purpose.
const AUTH_STORAGE_KEY = "attendance-admin-auth";

type TokenResponse = {
  access_token: string;
  refresh_token: string;
};

export function apiUrl(path: string): string {
  // Backend sometimes returns relative endpoints like "/api/v1/..."
  // Convert those to absolute URLs using NEXT_PUBLIC_API_BASE_URL.
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  return `${API_BASE}${path.startsWith("/") ? "" : "/"}${path}`;
}

type Persisted<T> = { state: T; version?: number };

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

function authToken(): string | null {
  const auth = loadPersistedState<{ accessToken?: string }>(AUTH_STORAGE_KEY);
  return auth?.accessToken ?? null;
}

function refreshToken(): string | null {
  const auth = loadPersistedState<{ refreshToken?: string }>(AUTH_STORAGE_KEY);
  return auth?.refreshToken ?? null;
}

function saveAuthTokens(next: TokenResponse): void {
  if (typeof window === "undefined") return;
  try {
    const current =
      loadPersistedState<Record<string, unknown>>(AUTH_STORAGE_KEY) ?? {};
    const updated = {
      ...current,
      accessToken: next.access_token,
      refreshToken: next.refresh_token,
    };
    window.localStorage.setItem(
      AUTH_STORAGE_KEY,
      JSON.stringify({ state: updated, version: 0 })
    );
  } catch {
    // Ignore storage errors (private mode / disabled storage).
  }
}

function clearAuthStorage(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(AUTH_STORAGE_KEY);
  } catch {
    // Ignore storage errors.
  }
}

function redirectToLoginIfNeeded(): void {
  if (typeof window === "undefined") return;
  if (window.location.pathname === "/login") return;
  window.location.assign("/login");
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

function authHeaders(): Record<string, string> {
  const token = authToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

let refreshInFlight: Promise<boolean> | null = null;

async function tryRefreshAccessToken(): Promise<boolean> {
  if (refreshInFlight) return refreshInFlight;

  refreshInFlight = (async () => {
    const rt = refreshToken();
    if (!rt) return false;

    try {
      const res = await fetch(apiUrl("/api/v1/auth/refresh"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...scopeHeaders(),
        },
        body: JSON.stringify({ refresh_token: rt }),
        cache: "no-store",
      });

      if (!res.ok) return false;
      const raw = (await res.json()) as unknown;
      const unwrapped = unwrapOkEnvelope<TokenResponse>(raw);
      if (!unwrapped?.access_token || !unwrapped?.refresh_token) return false;
      saveAuthTokens(unwrapped);
      return true;
    } catch {
      return false;
    } finally {
      refreshInFlight = null;
    }
  })();

  return refreshInFlight;
}

async function readErrorBody(res: Response): Promise<string> {
  // FastAPI errors may be either legacy {"detail": "..."} or enterprise envelope:
  // {"ok": false, "error": {"code": "...", "message": "..."}}
  const text = await res.text();
  try {
    const json = JSON.parse(text) as Record<string, unknown>;
    if (json && typeof json === "object") {
      const ok = (json as any).ok;
      if (ok === false && (json as any).error) {
        const err = (json as any).error as any;
        const code = typeof err.code === "string" ? err.code : "error";
        const msg = typeof err.message === "string" ? err.message : "Request failed";
        return `${code}: ${msg}`;
      }
    }
    if (json && typeof json === "object" && "detail" in json) {
      const detail = (json as Record<string, unknown>).detail;
      return typeof detail === "string" ? detail : JSON.stringify(detail);
    }
  } catch {
    // Not JSON, return raw response
  }
  return text;
}

function unwrapOkEnvelope<T>(raw: unknown): T {
  if (raw && typeof raw === "object" && "ok" in (raw as any)) {
    const ok = (raw as any).ok;
    if (ok === true) return (raw as any).data as T;
    const err = (raw as any).error;
    if (err && typeof err === "object") {
      const code = (err as any).code ?? "error";
      const message = (err as any).message ?? "Request failed";
      throw new Error(`${code}: ${message}`);
    }
    throw new Error("Request failed");
  }
  return raw as T;
}

export async function apiJson<T>(path: string, init?: RequestInit): Promise<T> {
  const attempt = async (useAuth: boolean): Promise<Response> =>
    fetch(apiUrl(path), {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...scopeHeaders(),
        ...(useAuth ? authHeaders() : {}),
        ...(init?.headers ?? {}),
      },
      cache: "no-store",
    });

  let res = await attempt(true);
  if (res.status === 401) {
    const refreshed = await tryRefreshAccessToken();
    if (refreshed) {
      res = await attempt(true);
    } else {
      clearAuthStorage();
      redirectToLoginIfNeeded();
    }
  }

  if (!res.ok) {
    throw new Error(
      `${res.status} ${res.statusText}: ${await readErrorBody(res)}`
    );
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
  const attempt = async (): Promise<Response> =>
    fetch(apiUrl(path), {
      method: init?.method ?? "POST",
      ...init,
      body: form,
      headers: {
        ...scopeHeaders(),
        ...authHeaders(),
        ...(init?.headers ?? {}),
      },
      cache: "no-store",
    });

  let res = await attempt();
  if (res.status === 401) {
    const refreshed = await tryRefreshAccessToken();
    if (refreshed) {
      res = await attempt();
    } else {
      clearAuthStorage();
      redirectToLoginIfNeeded();
    }
  }

  if (!res.ok) {
    throw new Error(
      `${res.status} ${res.statusText}: ${await readErrorBody(res)}`
    );
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
   */
  const url = apiUrl(path);

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", url);

    const token = authToken();
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
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
      } else {
        reject(new Error(`Upload failed: ${xhr.status} ${xhr.responseText}`));
      }
    };

    xhr.onerror = () => reject(new Error("Upload network error"));
    xhr.send(form);
  });
}
