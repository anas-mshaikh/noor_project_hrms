import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { fireEvent, screen } from "@testing-library/react";

import type { MeResponse } from "@/lib/types";
import { ok } from "@/test/msw/builders/response";
import { server } from "@/test/msw/server";
import { renderWithProviders } from "@/test/utils/render";
import { seedScope, seedSession } from "@/test/utils/selection";

import AttendancePunchPage from "../page";

const SESSION: MeResponse = {
  user: { id: "u-emp", email: "employee@example.com", status: "ACTIVE" },
  roles: ["EMPLOYEE"],
  permissions: ["attendance:punch:read", "attendance:punch:submit"],
  scope: {
    tenant_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    company_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    branch_id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
    allowed_tenant_ids: ["aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"],
    allowed_company_ids: ["bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"],
    allowed_branch_ids: ["cccccccc-cccc-4ccc-8ccc-cccccccccccc"],
  },
};

describe("/attendance/punch", () => {
  it("loads punch state and supports punch in/out", async () => {
    let isIn = false;

    server.use(
      http.get("*/api/v1/attendance/me/punch-state", () =>
        HttpResponse.json(
          ok({
            today_business_date: "2026-03-04",
            is_punched_in: isIn,
            open_session_started_at: isIn ? new Date(0).toISOString() : null,
            base_minutes_today: 0,
            effective_minutes_today: 0,
            effective_status_today: "PRESENT",
          })
        )
      ),
      http.post("*/api/v1/attendance/me/punch-in", () => {
        isIn = true;
        return HttpResponse.json(
          ok({
            today_business_date: "2026-03-04",
            is_punched_in: true,
            open_session_started_at: new Date(0).toISOString(),
            base_minutes_today: 0,
            effective_minutes_today: 0,
            effective_status_today: "PRESENT",
          })
        );
      }),
      http.post("*/api/v1/attendance/me/punch-out", () => {
        isIn = false;
        return HttpResponse.json(
          ok({
            today_business_date: "2026-03-04",
            is_punched_in: false,
            open_session_started_at: null,
            base_minutes_today: 0,
            effective_minutes_today: 0,
            effective_status_today: "PRESENT",
          })
        );
      })
    );

    seedSession(SESSION);
    seedScope({
      tenantId: SESSION.scope.tenant_id,
      companyId: SESSION.scope.company_id,
      branchId: SESSION.scope.branch_id,
    });

    renderWithProviders(<AttendancePunchPage />);

    expect(await screen.findByRole("heading", { name: "Punch" })).toBeVisible();
    expect(await screen.findByRole("button", { name: "Punch in" })).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Punch in" }));
    expect(await screen.findByRole("button", { name: "Punch out" })).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Punch out" }));
    expect(await screen.findByRole("button", { name: "Punch in" })).toBeVisible();
  });
});

