import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { fireEvent, screen } from "@testing-library/react";

import type { MeResponse } from "@/lib/types";
import { ok } from "@/test/msw/builders/response";
import { server } from "@/test/msw/server";
import { renderWithProviders } from "@/test/utils/render";
import { seedSession } from "@/test/utils/selection";

import DmsExpiryPage from "../page";

const SESSION: MeResponse = {
  user: { id: "u-hr", email: "hr@example.com", status: "ACTIVE" },
  roles: ["HR"],
  permissions: ["dms:expiry:read"],
  scope: {
    tenant_id: "tttttttt-tttt-4ttt-8ttt-tttttttttttt",
    company_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    branch_id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
    allowed_tenant_ids: ["tttttttt-tttt-4ttt-8ttt-tttttttttttt"],
    allowed_company_ids: ["bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"],
    allowed_branch_ids: ["cccccccc-cccc-4ccc-8ccc-cccccccccccc"],
  },
};

describe("/dms/expiry", () => {
  it("renders expiry buckets, rules, and updates the horizon request", async () => {
    const requestedDays: string[] = [];

    server.use(
      http.get("*/api/v1/dms/expiry/upcoming", ({ request }) => {
        const days = new URL(request.url).searchParams.get("days") ?? "";
        requestedDays.push(days);
        return HttpResponse.json(
          ok({
            items: [
              {
                document_id: "doc-1",
                document_type_code: "PASSPORT",
                document_type_name: "Passport",
                owner_employee_id: "emp-1",
                expires_at: "2026-03-20",
                days_left: days === "7" ? 6 : 20,
                status: "VERIFIED",
              },
            ],
          }),
        );
      }),
      http.get("*/api/v1/dms/expiry/rules", () =>
        HttpResponse.json(
          ok({
            items: [
              {
                id: "rule-1",
                tenant_id: SESSION.scope.tenant_id,
                document_type_id: "type-1",
                document_type_code: "PASSPORT",
                document_type_name: "Passport",
                days_before: 30,
                is_active: true,
                created_at: new Date(0).toISOString(),
                updated_at: new Date(0).toISOString(),
              },
            ],
          }),
        ),
      ),
    );

    seedSession(SESSION);
    renderWithProviders(<DmsExpiryPage />);

    expect(await screen.findByText("Passport")).toBeVisible();
    expect(await screen.findByText("Notify 30 days before expiry")).toBeVisible();
    expect(requestedDays[0]).toBe("30");

    fireEvent.click(screen.getByRole("button", { name: "7 days" }));

    expect(await screen.findByText("Expiring in 6 days")).toBeVisible();
    expect(requestedDays).toContain("7");
  });
});
