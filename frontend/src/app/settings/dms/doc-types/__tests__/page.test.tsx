import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { fireEvent, screen } from "@testing-library/react";

import type { DmsDocumentTypeOut, MeResponse } from "@/lib/types";
import { fail, ok } from "@/test/msw/builders/response";
import { server } from "@/test/msw/server";
import { renderWithProviders } from "@/test/utils/render";
import { seedSession } from "@/test/utils/selection";

import DmsDocumentTypesPage from "../page";

const SESSION: MeResponse = {
  user: { id: "u-admin", email: "admin@example.com", status: "ACTIVE" },
  roles: ["ADMIN"],
  permissions: ["dms:document-type:read", "dms:document-type:write"],
  scope: {
    tenant_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    company_id: null,
    branch_id: null,
    allowed_tenant_ids: ["aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"],
    allowed_company_ids: [],
    allowed_branch_ids: [],
  },
};

describe("/settings/dms/doc-types", () => {
  it("shows empty state, creates a type, and edits it", async () => {
    const items: DmsDocumentTypeOut[] = [];

    server.use(
      http.get("*/api/v1/dms/document-types", () => HttpResponse.json(ok({ items }))),
      http.post("*/api/v1/dms/document-types", async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        const created: DmsDocumentTypeOut = {
          id: "11111111-1111-4111-8111-111111111111",
          tenant_id: SESSION.scope.tenant_id,
          code: String(body.code),
          name: String(body.name),
          requires_expiry: Boolean(body.requires_expiry),
          is_active: Boolean(body.is_active ?? true),
          created_at: new Date(0).toISOString(),
          updated_at: new Date(0).toISOString(),
        };
        items.push(created);
        return HttpResponse.json(ok(created));
      }),
      http.patch("*/api/v1/dms/document-types/:docTypeId", async ({ params, request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        const index = items.findIndex((item) => item.id === String(params.docTypeId));
        items[index] = {
          ...items[index],
          name: String(body.name),
          requires_expiry: Boolean(body.requires_expiry),
          is_active: Boolean(body.is_active),
          updated_at: new Date(1).toISOString(),
        };
        return HttpResponse.json(ok(items[index]));
      }),
    );

    seedSession(SESSION);
    renderWithProviders(<DmsDocumentTypesPage />);

    expect(await screen.findByText("No document types")).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Create document type" }));
    fireEvent.change(screen.getByLabelText("Code"), { target: { value: "ID" } });
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "National ID" } });
    fireEvent.click(screen.getByRole("button", { name: /^Create$/ }));

    expect(await screen.findByText("National ID")).toBeVisible();
    expect(await screen.findByText("ID")).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Government ID" } });
    fireEvent.click(screen.getByLabelText("Active"));
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText("Government ID")).toBeVisible();
    expect(await screen.findByText("INACTIVE")).toBeVisible();
  });

  it("shows an inline error state when the catalog request is forbidden", async () => {
    server.use(
      http.get("*/api/v1/dms/document-types", () =>
        HttpResponse.json(
          fail("forbidden", "Forbidden", { correlation_id: "cid-dms-types" }),
          { status: 403 },
        ),
      ),
    );

    seedSession(SESSION);
    renderWithProviders(<DmsDocumentTypesPage />);

    expect(await screen.findByText("Could not load data")).toBeVisible();
  });
});
