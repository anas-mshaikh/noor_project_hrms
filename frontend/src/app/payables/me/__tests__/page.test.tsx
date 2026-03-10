import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { fireEvent, screen, waitFor } from "@testing-library/react";

import type { MeResponse, PayableDaysOut } from "@/lib/types";
import { fail, ok } from "@/test/msw/builders/response";
import { server } from "@/test/msw/server";
import { renderWithProviders } from "@/test/utils/render";
import { seedSession } from "@/test/utils/selection";

import PayablesMePage from "../page";

const SESSION: MeResponse = {
  user: { id: "u-ess", email: "employee@example.com", status: "ACTIVE" },
  roles: ["EMPLOYEE"],
  permissions: ["attendance:payable:read"],
  scope: {
    tenant_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    company_id: null,
    branch_id: null,
    allowed_tenant_ids: ["aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"],
    allowed_company_ids: [],
    allowed_branch_ids: [],
  },
};

describe("/payables/me", () => {
  it("queries the selected range and renders details", async () => {
    const requests: string[] = [];

    server.use(
      http.get("*/api/v1/attendance/me/payable-days", ({ request }) => {
        const url = new URL(request.url);
        requests.push(url.search);
        const out: PayableDaysOut = {
          items: [
            {
              day: url.searchParams.get("from") ?? "2026-01-01",
              employee_id: "11111111-1111-4111-8111-111111111111",
              branch_id: "22222222-2222-4222-8222-222222222222",
              shift_template_id: null,
              day_type: "WORKDAY",
              presence_status: "PRESENT",
              expected_minutes: 480,
              worked_minutes: 450,
              payable_minutes: 450,
              anomalies_json: null,
              source_breakdown: null,
              computed_at: new Date(0).toISOString(),
            },
          ],
        };
        return HttpResponse.json(ok(out));
      }),
    );

    seedSession(SESSION);
    renderWithProviders(<PayablesMePage />);

    expect(await screen.findByText("Payable Days")).toBeVisible();

    fireEvent.change(screen.getByLabelText("From"), { target: { value: "2026-02-01" } });
    fireEvent.change(screen.getByLabelText("To"), { target: { value: "2026-02-05" } });

    expect((await screen.findAllByText("2026-02-01")).length).toBeGreaterThan(0);
    await waitFor(() => {
      expect(requests.some((value) => value.includes("from=2026-02-01") && value.includes("to=2026-02-05"))).toBe(true);
    });
  });

  it("shows guided copy for calendar missing errors", async () => {
    server.use(
      http.get("*/api/v1/attendance/me/payable-days", () =>
        HttpResponse.json(
          fail("attendance.payable.calendar_missing", "Calendar missing", { correlation_id: "cid-payable" }),
          { status: 409 },
        ),
      ),
    );

    seedSession(SESSION);
    renderWithProviders(<PayablesMePage />);

    expect(await screen.findByText("Work calendar missing")).toBeVisible();
    expect(await screen.findByText(/cid-payable/)).toBeVisible();
  });
});
