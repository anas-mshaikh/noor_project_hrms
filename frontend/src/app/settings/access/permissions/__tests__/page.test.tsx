import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { fireEvent, screen } from "@testing-library/react";

import { server } from "@/test/msw/server";
import { renderWithProviders } from "@/test/render";

import PermissionsPage from "../page";

describe("/settings/access/permissions", () => {
  it("renders permission groups and supports searching", async () => {
    server.use(
      http.get("*/api/v1/iam/permissions", () =>
        HttpResponse.json({
          ok: true,
          data: [
            { code: "tenancy:read", description: "Read tenancy masters" },
            { code: "tenancy:write", description: "Write tenancy masters" },
            { code: "iam:user:read", description: "Read users" },
          ],
        })
      )
    );

    renderWithProviders(<PermissionsPage />);

    expect(await screen.findByText("tenancy:read")).toBeVisible();
    expect(screen.getByText("iam:user:read")).toBeVisible();

    fireEvent.change(screen.getByPlaceholderText(/search permission codes/i), {
      target: { value: "iam:" },
    });

    expect(await screen.findByText("iam:user:read")).toBeVisible();
    expect(screen.queryByText("tenancy:read")).not.toBeInTheDocument();
  });
});

