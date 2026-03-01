import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";

import { renderWithProviders } from "@/test/render";

import OrgUnitsPage from "../page";

describe("/settings/org/org-units", () => {
  it("prompts to select a company when none is selected", async () => {
    renderWithProviders(<OrgUnitsPage />);
    expect(await screen.findByText("Select a company")).toBeVisible();
    expect(screen.getByRole("link", { name: /go to scope/i })).toBeVisible();
  });
});

