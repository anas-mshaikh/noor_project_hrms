import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { screen } from "@testing-library/react";

import { server } from "@/test/msw/server";
import { renderWithProviders } from "@/test/render";

import RolesPage from "../page";

describe("/settings/access/roles", () => {
  it("renders roles from the catalog", async () => {
    server.use(
      http.get("*/api/v1/iam/roles", () =>
        HttpResponse.json({
          ok: true,
          data: [
            { code: "ADMIN", name: "Admin", description: "Full access" },
            { code: "EMPLOYEE", name: "Employee", description: null },
          ],
        })
      )
    );

    renderWithProviders(<RolesPage />);
    expect(await screen.findByText("ADMIN")).toBeVisible();
    expect(screen.getByText("Employee")).toBeVisible();
  });
});

