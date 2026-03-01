import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";

import { renderWithProviders } from "@/test/render";

import GradesPage from "../page";

describe("/settings/org/grades", () => {
  it("prompts to select a company when none is selected", async () => {
    renderWithProviders(<GradesPage />);
    expect(await screen.findByText("Select a company")).toBeVisible();
  });
});

