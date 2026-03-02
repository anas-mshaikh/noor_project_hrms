import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { FolderOpen } from "lucide-react";

import { renderWithProviders } from "@/test/render";
import { EmptyState } from "@/components/ds/EmptyState";

describe("EmptyState", () => {
  it("renders with a Lucide icon component (forwardRef)", () => {
    renderWithProviders(<EmptyState icon={FolderOpen} title="Empty" />);
    expect(screen.getByText("Empty")).toBeVisible();
  });

  it("renders with an explicit ReactNode icon", () => {
    renderWithProviders(
      <EmptyState icon={<FolderOpen className="h-5 w-5" />} title="Empty" />
    );
    expect(screen.getByText("Empty")).toBeVisible();
  });
});

