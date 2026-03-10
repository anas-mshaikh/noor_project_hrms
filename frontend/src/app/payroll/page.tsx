"use client";

import * as React from "react";
import Link from "next/link";

import { useAuth } from "@/lib/auth";
import { useSelection } from "@/lib/selection";
import { usePayrollCalendars, usePayrollComponents } from "@/features/payroll/hooks";
import { PayrollSummaryCard } from "@/features/payroll/components/PayrollSummaryCard";

import { DSCard } from "@/components/ds/DSCard";
import { EmptyState } from "@/components/ds/EmptyState";
import { ErrorState } from "@/components/ds/ErrorState";
import { PageHeader } from "@/components/ds/PageHeader";
import { Button } from "@/components/ui/button";

const PAYROLL_PERMISSIONS = [
  "payroll:calendar:read",
  "payroll:calendar:write",
  "payroll:component:read",
  "payroll:component:write",
  "payroll:structure:read",
  "payroll:structure:write",
  "payroll:compensation:read",
  "payroll:compensation:write",
  "payroll:payrun:read",
  "payroll:payrun:generate",
  "payroll:payrun:submit",
  "payroll:payrun:publish",
  "payroll:payrun:export",
];

function hasAnyPermission(granted: Set<string>): boolean {
  return PAYROLL_PERMISSIONS.some((permission) => granted.has(permission));
}

export default function PayrollHomePage() {
  const user = useAuth((s) => s.user);
  const permissions = useAuth((s) => s.permissions);
  const granted = React.useMemo(() => new Set(permissions ?? []), [permissions]);
  const canView = hasAnyPermission(granted);

  const calendarsQ = usePayrollCalendars(Boolean(user && granted.has("payroll:calendar:read")));
  const componentsQ = usePayrollComponents(null, Boolean(user && granted.has("payroll:component:read")));

  const companyId = useSelection((s) => s.companyId);
  const branchId = useSelection((s) => s.branchId);

  if (!user) {
    return (
      <ErrorState
        title="Sign in required"
        error={new Error("Please sign in to access payroll.")}
        details={
          <Button asChild variant="secondary">
            <Link href="/login">Sign in</Link>
          </Button>
        }
      />
    );
  }

  if (!canView) {
    return (
      <ErrorState
        title="Access denied"
        error={new Error("Your account does not have access to payroll.")}
      />
    );
  }

  const calendars = calendarsQ.data ?? [];
  const components = componentsQ.data ?? [];
  const activeCalendar = calendars.find((calendar) => calendar.is_active) ?? null;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Payroll"
        subtitle="Tenant payroll setup, payrun generation, and published payslips."
      />

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <PayrollSummaryCard
          label="Active calendar"
          value={activeCalendar ? activeCalendar.name : "Not set"}
          hint={activeCalendar ? activeCalendar.code : "Create a calendar to start period setup"}
        />
        <PayrollSummaryCard
          label="Calendars"
          value={calendarsQ.isLoading ? "Loading..." : String(calendars.length)}
          hint="Monthly payroll calendars"
        />
        <PayrollSummaryCard
          label="Components"
          value={componentsQ.isLoading ? "Loading..." : String(components.length)}
          hint="Earnings and deductions"
        />
        <PayrollSummaryCard
          label="Branch scope"
          value={branchId ? "Ready" : "Not selected"}
          hint={branchId ? branchId : "Payrun generation requires an active branch"}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <DSCard surface="card" className="space-y-4 p-[var(--ds-space-20)] lg:col-span-2">
          <div>
            <div className="text-sm font-semibold tracking-tight text-text-1">Setup checklist</div>
            <div className="mt-1 text-sm text-text-2">
              The backend does not expose payroll dashboard totals or browse endpoints for structures/payruns, so this checklist links directly to the supported setup surfaces.
            </div>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <Link className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-4 hover:bg-surface-2" href="/payroll/calendars">
              <div className="text-sm font-medium text-text-1">Calendars and periods</div>
              <div className="mt-1 text-xs text-text-2">{calendars.length > 0 ? `${calendars.length} configured` : "Create your first payroll calendar"}</div>
            </Link>
            <Link className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-4 hover:bg-surface-2" href="/payroll/components">
              <div className="text-sm font-medium text-text-1">Components</div>
              <div className="mt-1 text-xs text-text-2">{components.length > 0 ? `${components.length} configured` : "Create earnings and deductions"}</div>
            </Link>
            <Link className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-4 hover:bg-surface-2" href="/payroll/structures">
              <div className="text-sm font-medium text-text-1">Salary structures</div>
              <div className="mt-1 text-xs text-text-2">Create a structure, then add lines on its detail page.</div>
            </Link>
            <Link className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-4 hover:bg-surface-2" href="/payroll/compensation">
              <div className="text-sm font-medium text-text-1">Employee compensation</div>
              <div className="mt-1 text-xs text-text-2">Assign structures and effective-dated base pay per employee.</div>
            </Link>
            <Link className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-4 hover:bg-surface-2" href="/payroll/payruns">
              <div className="text-sm font-medium text-text-1">Payruns</div>
              <div className="mt-1 text-xs text-text-2">Generate, submit for approval, publish, and export payroll runs.</div>
            </Link>
            <Link className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-4 hover:bg-surface-2" href="/workflow/inbox">
              <div className="text-sm font-medium text-text-1">Workflow Inbox</div>
              <div className="mt-1 text-xs text-text-2">Approve or reject payrun approval requests.</div>
            </Link>
          </div>
        </DSCard>

        <DSCard surface="panel" className="space-y-4 p-[var(--ds-space-20)]">
          <div>
            <div className="text-sm font-semibold tracking-tight text-text-1">Current scope</div>
            <div className="mt-1 text-sm text-text-2">
              Payroll setup is tenant-scoped. Payrun generation also requires an active company and branch selection.
            </div>
          </div>
          <div className="space-y-2 text-sm text-text-2">
            <div>Company: {companyId ?? "Not selected"}</div>
            <div>Branch: {branchId ?? "Not selected"}</div>
          </div>
          {!branchId ? (
            <EmptyState
              title="Select a branch for payruns"
              description="Use Scope to choose the branch you want to generate payroll for."
              primaryAction={
                <Button asChild variant="secondary">
                  <Link href="/scope">Go to scope</Link>
                </Button>
              }
              align="center"
            />
          ) : null}
        </DSCard>
      </div>
    </div>
  );
}
