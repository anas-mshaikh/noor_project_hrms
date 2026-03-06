import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { fireEvent, screen, waitFor } from "@testing-library/react";

import type { AttendanceCorrectionListOut, AttendanceCorrectionOut, MeResponse } from "@/lib/types";
import { ok } from "@/test/msw/builders/response";
import { server } from "@/test/msw/server";
import { renderWithProviders } from "@/test/utils/render";
import { seedSession } from "@/test/utils/selection";

import AttendanceCorrectionsPage from "../page";

const SESSION: MeResponse = {
  user: { id: "u-emp", email: "employee@example.com", status: "ACTIVE" },
  roles: ["EMPLOYEE"],
  permissions: ["attendance:correction:read", "attendance:correction:submit"],
  scope: {
    tenant_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    company_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    branch_id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
    allowed_tenant_ids: ["aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"],
    allowed_company_ids: ["bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"],
    allowed_branch_ids: ["cccccccc-cccc-4ccc-8ccc-cccccccccccc"],
  },
};

describe("/attendance/corrections", () => {
  it("renders corrections and supports canceling a pending correction", async () => {
    const CORR_ID = "11111111-1111-4111-8111-111111111111";
    const base: AttendanceCorrectionOut = {
      id: CORR_ID,
      tenant_id: "t-1",
      employee_id: "e-1",
      branch_id: "b-1",
      day: "2026-03-01",
      correction_type: "MARK_PRESENT",
      requested_override_status: "PRESENT_OVERRIDE",
      reason: "missed punch",
      evidence_file_ids: [],
      status: "PENDING",
      workflow_request_id: null,
      idempotency_key: null,
      created_at: new Date(0).toISOString(),
      updated_at: new Date(0).toISOString(),
    };

    server.use(
      http.get("*/api/v1/attendance/me/corrections", () => {
        const out: AttendanceCorrectionListOut = { items: [base], next_cursor: null };
        return HttpResponse.json(ok(out));
      }),
      http.post("*/api/v1/attendance/me/corrections/:id/cancel", ({ params }) => {
        expect(String(params.id)).toBe(CORR_ID);
        return HttpResponse.json(ok({ ...base, status: "CANCELED" }));
      })
    );

    seedSession(SESSION);
    renderWithProviders(<AttendanceCorrectionsPage />);

    expect(await screen.findByText("2026-03-01")).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(await screen.findByRole("dialog", { name: /cancel correction/i })).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Cancel correction" }));

    // Sheet should close on success.
    await waitFor(() => {
      expect(screen.queryByRole("dialog", { name: /cancel correction/i })).toBeNull();
    });
  });
});
