import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { fireEvent, screen } from "@testing-library/react";

import { ymdFromDateLocal } from "@/lib/dateRange";
import type { MeResponse } from "@/lib/types";
import { ok } from "@/test/msw/builders/response";
import { server } from "@/test/msw/server";
import { renderWithProviders } from "@/test/utils/render";
import { seedSession } from "@/test/utils/selection";

import AttendanceDaysPage from "../page";

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

describe("/attendance/days", () => {
  it("renders days and opens a day detail panel", async () => {
    const now = new Date();
    const day1 = ymdFromDateLocal(new Date(now.getFullYear(), now.getMonth(), 1));
    const day2 = ymdFromDateLocal(new Date(now.getFullYear(), now.getMonth(), 2));

    server.use(
      http.get("*/api/v1/attendance/me/days", () =>
        HttpResponse.json(
          ok({
            items: [
              {
                day: day1,
                base_status: "ABSENT",
                effective_status: "PRESENT_OVERRIDE",
                base_minutes: 0,
                effective_minutes: 480,
                first_in: null,
                last_out: null,
                has_open_session: false,
                sources: ["CORRECTION"],
                override: {
                  kind: "CORRECTION",
                  status: "PRESENT_OVERRIDE",
                  source_type: "ATTENDANCE_CORRECTION",
                  source_id: "11111111-1111-4111-8111-111111111111",
                },
              },
              {
                day: day2,
                base_status: "PRESENT",
                effective_status: "PRESENT",
                base_minutes: 510,
                effective_minutes: 510,
                first_in: `${day2}T09:00:00Z`,
                last_out: `${day2}T17:30:00Z`,
                has_open_session: false,
                sources: ["PUNCH"],
                override: null,
              },
            ],
          })
        )
      )
    );

    seedSession(SESSION);
    renderWithProviders(<AttendanceDaysPage />);

    expect(await screen.findByText(day1)).toBeVisible();
    expect(screen.getByText(day2)).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: day1 }));

    const link = await screen.findByRole("link", { name: "Request correction" });
    expect(link).toHaveAttribute("href", `/attendance/corrections/new?day=${day1}`);
  });
});
