import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api";
import { useSelection } from "@/lib/selection";
import { ErrorState } from "@/components/ds/ErrorState";
import { renderWithProviders } from "@/test/utils/render";
import { seedScope } from "@/test/utils/selection";

describe("ErrorState", () => {
  it("copies the correlation reference", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });

    renderWithProviders(
      <ErrorState
        title="Failure"
        error={new ApiError({
          status: 409,
          code: "workflow.step.already_decided",
          correlationId: "cid-copy-1",
          message: "Already finalized",
        })}
      />
    );

    await user.click(await screen.findByRole("button", { name: "Copy ref" }));

    expect(writeText).toHaveBeenCalledWith("cid-copy-1");
    expect(await screen.findByRole("button", { name: "Copied" })).toBeVisible();
  });

  it("resets scope selection before routing to scope recovery", async () => {
    const user = userEvent.setup();
    seedScope({ tenantId: "tenant-a", companyId: "company-a", branchId: "branch-a" });

    renderWithProviders(
      <ErrorState
        title="Failure"
        error={new ApiError({
          status: 403,
          code: "iam.scope.forbidden",
          correlationId: "cid-scope-1",
          message: "Forbidden scope",
        })}
      />
    );

    await user.click(await screen.findByRole("button", { name: "Reset selection" }));

    expect(useSelection.getState().tenantId).toBeUndefined();
    expect(useSelection.getState().companyId).toBeUndefined();
    expect(useSelection.getState().branchId).toBeUndefined();
  });
});
