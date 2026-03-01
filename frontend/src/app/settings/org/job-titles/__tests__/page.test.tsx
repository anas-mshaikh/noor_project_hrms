import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";

import { renderWithProviders } from "@/test/render";

import JobTitlesPage from "../page";

describe("/settings/org/job-titles", () => {
  it("prompts to select a company when none is selected", async () => {
    renderWithProviders(<JobTitlesPage />);
    expect(await screen.findByText("Select a company")).toBeVisible();
  });
});

