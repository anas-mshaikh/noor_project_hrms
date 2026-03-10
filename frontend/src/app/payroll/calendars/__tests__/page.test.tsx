import { describe, expect, it } from "vitest";
import { fireEvent, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type { MeResponse, PayrollCalendarOut, PayrollPeriodOut } from "@/lib/types";
import { ok } from "@/test/msw/builders/response";
import { server } from "@/test/msw/server";
import { renderWithProviders } from "@/test/utils/render";
import { seedSession } from "@/test/utils/selection";

import PayrollCalendarsPage from "../page";

const TENANT_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const CALENDAR_ID = "11111111-1111-4111-8111-111111111111";
const SESSION: MeResponse = {
  user: { id: "u-payroll", email: "payroll@example.com", status: "ACTIVE" },
  roles: ["HR"],
  permissions: ["payroll:calendar:read", "payroll:calendar:write"],
  scope: {
    tenant_id: TENANT_ID,
    company_id: null,
    branch_id: null,
    allowed_tenant_ids: [TENANT_ID],
    allowed_company_ids: [],
    allowed_branch_ids: [],
  },
};

function calendar(code = "MONTHLY", name = "Monthly Payroll"): PayrollCalendarOut {
  const now = new Date(0).toISOString();
  return {
    id: CALENDAR_ID,
    tenant_id: TENANT_ID,
    code,
    name,
    frequency: "MONTHLY",
    currency_code: "SAR",
    timezone: "Asia/Riyadh",
    is_active: true,
    created_by_user_id: null,
    created_at: now,
    updated_at: now,
  };
}

function period(key = "2026-03"): PayrollPeriodOut {
  const now = new Date(0).toISOString();
  return {
    id: "22222222-2222-4222-8222-222222222222",
    tenant_id: TENANT_ID,
    calendar_id: CALENDAR_ID,
    period_key: key,
    start_date: "2026-03-01",
    end_date: "2026-03-31",
    status: "OPEN",
    created_at: now,
    updated_at: now,
  };
}

describe("/payroll/calendars", () => {
  it("creates a calendar and a period", async () => {
    const calendars: PayrollCalendarOut[] = [];
    const periods: PayrollPeriodOut[] = [];

    server.use(
      http.get("*/api/v1/payroll/calendars", () => HttpResponse.json(ok(calendars))),
      http.post("*/api/v1/payroll/calendars", async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        const created = calendar(String(body.code ?? "MONTHLY"), String(body.name ?? "Monthly Payroll"));
        calendars.push(created);
        return HttpResponse.json(ok(created));
      }),
      http.get(`*/api/v1/payroll/calendars/${CALENDAR_ID}/periods`, () =>
        HttpResponse.json(ok(periods)),
      ),
      http.post(`*/api/v1/payroll/calendars/${CALENDAR_ID}/periods`, async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        const created = {
          ...period(String(body.period_key ?? "2026-03")),
          start_date: String(body.start_date ?? "2026-03-01"),
          end_date: String(body.end_date ?? "2026-03-31"),
        };
        periods.push(created);
        return HttpResponse.json(ok(created));
      }),
    );

    seedSession(SESSION);
    renderWithProviders(<PayrollCalendarsPage />);

    expect(await screen.findByText("No payroll calendars")).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Create calendar" }));
    fireEvent.change(screen.getByLabelText("Code"), { target: { value: "MONTHLY" } });
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Monthly Payroll" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Create calendar" })[1]);

    expect((await screen.findAllByText("Monthly Payroll")).length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "Create period" }));
    fireEvent.change(screen.getByLabelText("Period key"), { target: { value: "2026-03" } });
    fireEvent.change(screen.getByLabelText("Start date"), { target: { value: "2026-03-01" } });
    fireEvent.change(screen.getByLabelText("End date"), { target: { value: "2026-03-31" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Create period" })[1]);

    expect(await screen.findByText("2026-03")).toBeVisible();
  });
});
