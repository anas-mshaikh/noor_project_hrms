import { act, screen } from "@testing-library/react";
import { useQuery } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";

import { useSelection } from "@/lib/selection";
import { renderWithProviders } from "@/test/utils/render";
import { seedScope } from "@/test/utils/selection";

function DemoScopeQuery() {
  const companyId = useSelection((s) => s.companyId) ?? "none";
  const query = useQuery({
    queryKey: ["demo-scope-query"],
    queryFn: async () => useSelection.getState().companyId ?? "none",
  });

  return (
    <div>
      <div>{`scope=${companyId}`}</div>
      <div>{`query=${query.data ?? "loading"}`}</div>
    </div>
  );
}

describe("ScopeQueryReset", () => {
  it("clears cached queries when the selected scope changes", async () => {
    seedScope({ tenantId: "tenant-a", companyId: "company-a", branchId: "branch-a" });

    renderWithProviders(<DemoScopeQuery />);

    expect(await screen.findByText("scope=company-a")).toBeVisible();
    expect(await screen.findByText("query=company-a")).toBeVisible();

    act(() => {
      useSelection.getState().setCompanyId("company-b");
    });

    expect(await screen.findByText("scope=company-b")).toBeVisible();
    expect(await screen.findByText("query=company-b")).toBeVisible();
  });
});
