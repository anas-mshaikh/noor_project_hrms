import { describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import * as api from "@/lib/api";
import type { MeResponse, PayslipOut } from "@/lib/types";
import { ok } from "@/test/msw/builders/response";
import { server } from "@/test/msw/server";
import { renderWithProviders } from "@/test/utils/render";
import { setSearchParams } from "@/test/utils/router";
import { seedSession } from "@/test/utils/selection";

import EssPayslipsPage from "../page";

const TENANT_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const PAYSLIP_ID = "99999999-9999-4999-8999-999999999999";
const SESSION: MeResponse = {
  user: { id: "u-ess", email: "employee@example.com", status: "ACTIVE" },
  roles: ["EMPLOYEE"],
  permissions: ["payroll:payslip:read"],
  scope: {
    tenant_id: TENANT_ID,
    company_id: null,
    branch_id: null,
    allowed_tenant_ids: [TENANT_ID],
    allowed_company_ids: [],
    allowed_branch_ids: [],
  },
};

function payslip(id = PAYSLIP_ID): PayslipOut {
  const now = new Date(0).toISOString();
  return {
    id,
    tenant_id: TENANT_ID,
    payrun_id: "77777777-7777-4777-8777-777777777777",
    employee_id: "employee-1",
    status: "PUBLISHED",
    dms_document_id: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
    period_key: "2026-03",
    created_at: now,
    updated_at: now,
  };
}

describe("/ess/payslips", () => {
  it("loads payslips and downloads the selected payslip", async () => {
    const saveSpy = vi.spyOn(api, "saveBlobAsFile").mockImplementation(() => {});

    server.use(
      http.get("*/api/v1/ess/me/payslips", () => HttpResponse.json(ok({ items: [payslip()] }))),
      http.get(`*/api/v1/ess/me/payslips/${PAYSLIP_ID}`, () => HttpResponse.json(ok(payslip()))),
      http.get(`*/api/v1/ess/me/payslips/${PAYSLIP_ID}/download`, () =>
        new HttpResponse(JSON.stringify({ id: PAYSLIP_ID }), {
          status: 200,
          headers: {
            "Content-Type": "application/json",
            "Content-Disposition": 'attachment; filename="payslip_2026-03.json"',
          },
        }),
      ),
    );

    seedSession(SESSION);
    setSearchParams({ payslipId: PAYSLIP_ID, year: 2026 });

    renderWithProviders(<EssPayslipsPage />);

    expect(await screen.findByText("2026-03")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Download payslip" }));
    await waitFor(() => expect(saveSpy).toHaveBeenCalled());

    saveSpy.mockRestore();
  });

  it("shows neutral not-found copy for inaccessible payslips", async () => {
    server.use(
      http.get("*/api/v1/ess/me/payslips", () => HttpResponse.json(ok({ items: [] }))),
      http.get(`*/api/v1/ess/me/payslips/${PAYSLIP_ID}`, () =>
        HttpResponse.json(
          {
            ok: false,
            error: {
              code: "payroll.payslip.not_found",
              message: "Not found",
              correlation_id: "cid-payslip",
            },
          },
          { status: 404 },
        ),
      ),
    );

    seedSession(SESSION);
    setSearchParams({ payslipId: PAYSLIP_ID, year: 2026 });

    renderWithProviders(<EssPayslipsPage />);

    expect(await screen.findByText("Not found")).toBeVisible();
    expect(screen.getByText("This payslip does not exist or is not accessible.")).toBeVisible();
  });
});
