import { describe, expect, it } from "vitest";

import { ApiError } from "./api";
import { getErrorUx } from "./errorUx";

describe("lib/errorUx", () => {
  it("maps tenant_required to go_scope", () => {
    const err = new ApiError({
      status: 400,
      code: "iam.scope.tenant_required",
      message: "Tenant required",
      correlationId: "cid",
    });
    expect(getErrorUx(err)).toMatchObject({ suggestedActionKind: "go_scope" });
  });

  it("maps forbidden scope to reset_scope", () => {
    const err = new ApiError({
      status: 403,
      code: "iam.scope.forbidden",
      message: "Forbidden",
      correlationId: "cid",
    });
    expect(getErrorUx(err)).toMatchObject({ suggestedActionKind: "reset_scope" });
  });

  it("maps 401 to go_login", () => {
    const err = new ApiError({
      status: 401,
      code: "unauthorized",
      message: "Unauthorized",
      correlationId: "cid",
    });
    expect(getErrorUx(err)).toMatchObject({ suggestedActionKind: "go_login" });
  });

  it("maps network errors to retry", () => {
    const err = new ApiError({
      status: 0,
      code: "network_error",
      message: "Network error",
      isNetworkError: true,
    });
    expect(getErrorUx(err)).toMatchObject({ suggestedActionKind: "retry" });
  });

  it("maps workflow assignee errors to Not allowed", () => {
    const err = new ApiError({
      status: 403,
      code: "workflow.step.not_assignee",
      message: "Not an assignee",
      correlationId: "cid",
    });
    expect(getErrorUx(err)).toMatchObject({ title: "Not allowed" });
  });

  it("maps attendance correction conflicts to friendly copy", () => {
    const err = new ApiError({
      status: 409,
      code: "attendance.correction.pending_exists",
      message: "Pending exists",
      correlationId: "cid",
    });
    expect(getErrorUx(err)).toMatchObject({ title: "Correction already pending" });
  });

  it("maps leave overlap to friendly copy", () => {
    const err = new ApiError({
      status: 409,
      code: "leave.overlap",
      message: "Overlap",
      correlationId: "cid",
    });
    expect(getErrorUx(err)).toMatchObject({ title: "Overlapping leave" });
  });

  it("maps DMS document not found to neutral copy", () => {
    const err = new ApiError({
      status: 404,
      code: "dms.document.not_found",
      message: "Document not found",
      correlationId: "cid",
    });
    expect(getErrorUx(err)).toMatchObject({ title: "Not found" });
  });

  it("maps DMS version conflicts to retry guidance", () => {
    const err = new ApiError({
      status: 409,
      code: "dms.document.version.conflict",
      message: "Conflict",
      correlationId: "cid",
    });
    expect(getErrorUx(err)).toMatchObject({ suggestedActionKind: "retry" });
  });

  it("maps roster overlap to friendly copy", () => {
    const err = new ApiError({
      status: 409,
      code: "roster.assignment.overlap",
      message: "Overlap",
      correlationId: "cid",
    });
    expect(getErrorUx(err)).toMatchObject({ title: "Overlapping assignment" });
  });

  it("maps payables calendar missing to friendly copy", () => {
    const err = new ApiError({
      status: 409,
      code: "attendance.payable.calendar_missing",
      message: "Calendar missing",
      correlationId: "cid",
    });
    expect(getErrorUx(err)).toMatchObject({ title: "Work calendar missing" });
  });

  it("maps payroll compensation overlap to friendly copy", () => {
    const err = new ApiError({
      status: 409,
      code: "payroll.compensation.overlap",
      message: "Overlap",
      correlationId: "cid",
    });
    expect(getErrorUx(err)).toMatchObject({ title: "Overlapping compensation" });
  });

  it("maps payroll workflow definition missing to guided copy", () => {
    const err = new ApiError({
      status: 409,
      code: "workflow.definition.no_active",
      message: "No active workflow definition",
      correlationId: "cid",
    });
    expect(getErrorUx(err)).toMatchObject({
      title: "Approval workflow not configured",
    });
  });
});
