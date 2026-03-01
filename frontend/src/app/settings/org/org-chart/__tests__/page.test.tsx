import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";

import { renderWithProviders } from "@/test/render";

import OrgChartPage from "../page";

describe("/settings/org/org-chart", () => {
  it("prompts to select a company when none is selected", async () => {
    renderWithProviders(<OrgChartPage />);
    expect(await screen.findByText("Select a company")).toBeVisible();
    expect(screen.getByRole("link", { name: /go to scope/i })).toBeVisible();
  });
});

