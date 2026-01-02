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
 * - Video upload expects: PUT /stores/{store_id}/videos/{video_id}/file with FormData field name "file"
 * - Face upload expects: POST /employees/{employee_id}/faces with FormData field name "files" (multiple)
 */

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export function apiUrl(path: string): string {
  // Backend sometimes returns relative endpoints like "/api/v1/..."
  // Convert those to absolute URLs using NEXT_PUBLIC_API_BASE_URL.
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  return `${API_BASE}${path.startsWith("/") ? "" : "/"}${path}`;
}

async function readErrorBody(res: Response): Promise<string> {
  // FastAPI errors often look like: {"detail":"..."} or {"detail":[...]}
  const text = await res.text();
  try {
    const json = JSON.parse(text);
    if (json && typeof json === "object" && "detail" in json) {
      const detail = (json as any).detail;
      return typeof detail === "string" ? detail : JSON.stringify(detail);
    }
  } catch {
    // Not JSON, return raw response
  }
  return text;
}

export async function apiJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(apiUrl(path), {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });

  if (!res.ok) {
    throw new Error(
      `${res.status} ${res.statusText}: ${await readErrorBody(res)}`
    );
  }

  return (await res.json()) as T;
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
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });

  if (!res.ok) {
    throw new Error(
      `${res.status} ${res.statusText}: ${await readErrorBody(res)}`
    );
  }

  // Some endpoints might return JSON, some might return text; handle both.
  const text = await res.text();
  try {
    return JSON.parse(text) as T;
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

    xhr.upload.onprogress = (evt) => {
      if (!evt.lengthComputable) return;
      onProgress(Math.round((evt.loaded / evt.total) * 100));
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText) as T);
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
