import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { fireEvent, screen } from "@testing-library/react";

import type { AttendanceCorrectionOut, MeResponse } from "@/lib/types";
import { ok } from "@/test/msw/builders/response";
import { server } from "@/test/msw/server";
import { renderWithProviders } from "@/test/utils/render";
import { seedSession } from "@/test/utils/selection";
import { setSearchParams } from "@/test/utils/router";

import AttendanceCorrectionNewPage from "../page";

const SESSION: MeResponse = {
  user: { id: "u-emp", email: "employee@example.com", status: "ACTIVE" },
  roles: ["EMPLOYEE"],
  permissions: ["attendance:correction:submit"],
  scope: {
    tenant_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    company_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    branch_id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
    allowed_tenant_ids: ["aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"],
    allowed_company_ids: ["bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"],
    allowed_branch_ids: ["cccccccc-cccc-4ccc-8ccc-cccccccccccc"],
  },
};

describe("/attendance/corrections/new", () => {
  it("submits a correction and shows a workflow link", async () => {
    const WORKFLOW_ID = "22222222-2222-4222-8222-222222222222";

    server.use(
      http.post("*/api/v1/attendance/me/corrections", async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        expect(body.day).toBe("2026-03-01");
        expect(body.correction_type).toBe("MARK_PRESENT");
        expect(body.requested_override_status).toBe("PRESENT_OVERRIDE");

        const out: AttendanceCorrectionOut = {
          id: "11111111-1111-4111-8111-111111111111",
          tenant_id: "t-1",
          employee_id: "e-1",
          branch_id: "b-1",
          day: "2026-03-01",
          correction_type: "MARK_PRESENT",
          requested_override_status: "PRESENT_OVERRIDE",
          reason: "missed punch",
          evidence_file_ids: [],
          status: "PENDING",
          workflow_request_id: WORKFLOW_ID,
          idempotency_key: String(body.idempotency_key ?? ""),
          created_at: new Date(0).toISOString(),
          updated_at: new Date(0).toISOString(),
        };
        return HttpResponse.json(ok(out));
      })
    );

    seedSession(SESSION);
    setSearchParams({ day: "2026-03-01" });

    renderWithProviders(<AttendanceCorrectionNewPage />);

    // Reason is required in v1 UI.
    fireEvent.change(screen.getByLabelText("Reason"), { target: { value: "missed punch" } });
    fireEvent.click(screen.getByRole("button", { name: "Submit" }));

    const link = await screen.findByRole("link", { name: "View request" });
    expect(link).toHaveAttribute("href", `/workflow/requests/${WORKFLOW_ID}`);
  });
});

