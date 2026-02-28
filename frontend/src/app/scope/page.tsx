"use client";

/**
 * /scope
 *
 * Scope selection / remediation page for fail-closed multi-tenant scoping.
 *
 * The backend rejects requests when:
 * - X-Tenant-Id is required for multi-tenant users (`iam.scope.tenant_required`)
 * - user tries to access a company/branch not covered by their role assignments
 *   (`iam.scope.forbidden`)
 *
 * This page provides a clear UX for selecting the active tenant/company/branch.
 */

import { useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { StorePicker } from "@/components/StorePicker";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useSelection } from "@/lib/selection";

function reasonCopy(code: string | null): { title: string; body: string } {
  switch (code) {
    case "iam.scope.tenant_required":
      return {
        title: "Tenant selection required",
        body: "Your account can access multiple tenants. Select the tenant/company/branch you want to work in.",
      };
    case "iam.scope.forbidden":
    case "iam.scope.forbidden_tenant":
      return {
        title: "Scope not allowed",
        body: "Your current selection is not covered by your role assignments. Pick a different tenant/company/branch.",
      };
    case "iam.scope.mismatch":
      return {
        title: "Scope mismatch",
        body: "Your request scope did not match the selected scope. Re-select your tenant/company/branch and try again.",
      };
    case "iam.scope.invalid_tenant":
    case "iam.scope.invalid_company":
    case "iam.scope.invalid_branch":
      return {
        title: "Invalid selection",
        body: "Your selection is invalid or expired. Re-select your tenant/company/branch and try again.",
      };
    default:
      return {
        title: "Select context",
        body: "Pick tenant, company, and branch to continue.",
      };
  }
}

export default function ScopePage() {
  const router = useRouter();
  const params = useSearchParams();
  const resetSelection = useSelection((s) => s.reset);

  const reason = params.get("reason");
  const cid = params.get("cid");

  const copy = useMemo(() => reasonCopy(reason), [reason]);

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <Card className="border-white/10 bg-white/[0.03] backdrop-blur-xl">
        <CardHeader>
          <CardTitle className="tracking-tight">{copy.title}</CardTitle>
          <CardDescription className="text-muted-foreground">
            {copy.body}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {cid ? (
            <div className="rounded-xl border border-white/10 bg-white/[0.02] p-3 text-sm">
              <div className="text-muted-foreground">correlation_id</div>
              <div className="font-mono text-xs">{cid}</div>
            </div>
          ) : null}

          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-3">
            <StorePicker />
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button type="button" onClick={() => router.push("/dashboard")}>
              Continue
            </Button>
            <Button type="button" variant="secondary" onClick={() => router.push("/login")}>
              Sign in again
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                resetSelection();
                router.refresh();
              }}
            >
              Reset selection
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
