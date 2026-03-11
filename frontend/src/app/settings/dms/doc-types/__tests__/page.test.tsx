import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

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
    const user = userEvent.setup();
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

    await user.click(screen.getAllByRole("button", { name: "Create document type" })[0]);
    const createDialog = await screen.findByRole("dialog");
    await user.type(within(createDialog).getByLabelText("Code"), "ID");
    await user.type(within(createDialog).getByLabelText("Name"), "National ID");
    await user.click(within(createDialog).getByRole("button", { name: /^Create$/ }));

    expect(await screen.findByRole("cell", { name: "National ID" })).toBeVisible();
    expect(await screen.findByRole("cell", { name: "ID" })).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Edit" }));
    const editDialog = await screen.findByRole("dialog");
    await user.clear(within(editDialog).getByLabelText("Name"));
    await user.type(within(editDialog).getByLabelText("Name"), "Government ID");
    await user.click(within(editDialog).getByLabelText("Active"));
    await user.click(within(editDialog).getByRole("button", { name: "Save" }));

    expect(await screen.findByRole("cell", { name: "Government ID" })).toBeVisible();
    expect(await screen.findByText("INACTIVE")).toBeVisible();
  }, 45_000);

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

    expect(await screen.findByText("Not allowed")).toBeVisible();
  });
});
