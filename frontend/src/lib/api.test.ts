import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiDownload, apiJson, parseContentDispositionFilename } from "./api";
import { fail } from "@/test/msw/builders/response";

function jsonResponse(body: unknown, opts?: { status?: number; headers?: Record<string, string> }): Response {
  return new Response(JSON.stringify(body), {
    status: opts?.status ?? 200,
    headers: {
      "content-type": "application/json",
      ...(opts?.headers ?? {}),
    },
  });
}

describe("lib/api", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("prefers payload correlation_id over X-Correlation-Id header", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse(
          fail("iam.scope.forbidden", "Scope not allowed", { correlation_id: "payload-cid" }),
          { status: 403, headers: { "x-correlation-id": "header-cid" } }
        )
      )
    );

    await expect(apiJson("/api/v1/test")).rejects.toMatchObject({
      name: "ApiError",
      status: 403,
      code: "iam.scope.forbidden",
      correlationId: "payload-cid",
    });
  });

  it("falls back to X-Correlation-Id header when payload correlation_id missing", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse(
          fail("iam.scope.forbidden", "Scope not allowed"),
          { status: 403, headers: { "x-correlation-id": "header-cid" } }
        )
      )
    );

    await expect(apiJson("/api/v1/test")).rejects.toMatchObject({
      name: "ApiError",
      status: 403,
      code: "iam.scope.forbidden",
      correlationId: "header-cid",
    });
  });

  it("clears stale scope selection and redirects to /scope on scope errors", async () => {
    window.localStorage.setItem(
      "attendance-admin-selection",
      JSON.stringify({
        state: {
          tenantId: "tenant-a",
          companyId: "company-a",
          branchId: "branch-a",
          cameraId: "camera-a",
        },
        version: 0,
      })
    );

    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse(
          fail("iam.scope.forbidden", "Scope not allowed", { correlation_id: "cid-scope" }),
          { status: 403 }
        )
      )
    );

    await expect(apiJson("/api/v1/test")).rejects.toMatchObject({
      code: "iam.scope.forbidden",
      correlationId: "cid-scope",
    });

    expect(JSON.parse(window.localStorage.getItem("attendance-admin-selection") ?? "{}")).toMatchObject(
      {
        state: {
          tenantId: "tenant-a",
        },
      }
    );
  });

  it("treats ok:false on 2xx responses as an error with a sensible status", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse(
          fail("some.error", "Nope"),
          { status: 200, headers: { "x-correlation-id": "cid" } }
        )
      )
    );

    let thrown: unknown = null;
    try {
      await apiJson("/api/v1/test");
    } catch (e) {
      thrown = e;
    }

    expect(thrown).toBeInstanceOf(ApiError);
    const err = thrown as ApiError;
    expect(err.status).toBe(400);
    expect(err.code).toBe("some.error");
    expect(err.correlationId).toBe("cid");
  });

  it("apiDownload throws ApiError when server returns an envelope error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse(
          fail("vision.artifact.not_found", "Not found"),
          { status: 404, headers: { "x-correlation-id": "cid" } }
        )
      )
    );

    await expect(apiDownload("/api/v1/branches/b/artifacts/a/download")).rejects.toMatchObject({
      name: "ApiError",
      status: 404,
      code: "vision.artifact.not_found",
      correlationId: "cid",
    });
  });

  it("parses Content-Disposition filename* correctly", () => {
    expect(parseContentDispositionFilename("attachment; filename*=UTF-8''hello%20world.csv")).toBe(
      "hello world.csv"
    );
  });

  it("parses Content-Disposition filename correctly", () => {
    expect(parseContentDispositionFilename('attachment; filename="report.csv"')).toBe("report.csv");
  });
});
