"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/lib/auth";
import { parseUuidParam } from "@/lib/guards";
import { useSelection } from "@/lib/selection";
import { toastApiError } from "@/lib/toastApiError";
import type { PayrunGenerateIn, UUID } from "@/lib/types";
import { PayrollScopeState } from "@/features/payroll/components/PayrollScopeState";
import {
  usePayrunGenerate,
  usePayrollCalendars,
  usePayrollPeriods,
} from "@/features/payroll/hooks";
import { payrollKeys } from "@/features/payroll/queryKeys";
import { newPayrollIdempotencyKey } from "@/features/payroll/utils/idempotency";
import { currentPayrollYear } from "@/features/payroll/utils/periods";

import { DSCard } from "@/components/ds/DSCard";
import { EmptyState } from "@/components/ds/EmptyState";
import { ErrorState } from "@/components/ds/ErrorState";
import { PageHeader } from "@/components/ds/PageHeader";
import { RightPanelStack } from "@/components/ds/RightPanelStack";
import { ListRightPanelTemplate } from "@/components/ds/templates/ListRightPanelTemplate";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";

const selectClassName = [
  "h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm",
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
].join(" ");

export default function PayrollPayrunsPage() {
  const router = useRouter();
  const qc = useQueryClient();

  const permissions = useAuth((s) => s.permissions);
  const granted = React.useMemo(() => new Set(permissions ?? []), [permissions]);
  const canRead = granted.has("payroll:payrun:read") || granted.has("payroll:payrun:generate");
  const canGenerate = granted.has("payroll:payrun:generate");
  const canReadCalendars = granted.has("payroll:calendar:read");

  const companyId = parseUuidParam(useSelection((s) => s.companyId));
  const branchId = parseUuidParam(useSelection((s) => s.branchId));

  const calendarsQ = usePayrollCalendars(Boolean(canReadCalendars));
  const calendars = React.useMemo(() => calendarsQ.data ?? [], [calendarsQ.data]);
  const [calendarId, setCalendarId] = React.useState<UUID | null>(null);
  const [year, setYear] = React.useState(currentPayrollYear());
  const periodsQ = usePayrollPeriods(calendarId, year, Boolean(calendarId && canReadCalendars));
  const periods = periodsQ.data ?? [];

  React.useEffect(() => {
    if (!calendarId && calendars[0]) setCalendarId(calendars[0].id);
  }, [calendarId, calendars]);

  const [generateOpen, setGenerateOpen] = React.useState(false);
  const [periodKey, setPeriodKey] = React.useState("");
  const [openId, setOpenId] = React.useState("");
  const generateM = usePayrunGenerate();

  if (!canRead) {
    return (
      <ErrorState
        title="Access denied"
        error={new Error("Your account does not have access to payroll runs.")}
      />
    );
  }

  if (!companyId || !branchId) {
    return (
      <PayrollScopeState
        title="Select company and branch"
        description="Payruns are branch-scoped. Select both company and branch before generating a payrun."
      />
    );
  }

  async function onGenerate() {
    if (!calendarId) {
      toast.error("Select a payroll calendar.");
      return;
    }
    if (!periodKey) {
      toast.error("Select a payroll period.");
      return;
    }

    const payload: PayrunGenerateIn = {
      calendar_id: calendarId,
      period_key: periodKey,
      branch_id: branchId,
      idempotency_key: newPayrollIdempotencyKey("payrun"),
    };

    try {
      const created = await generateM.mutateAsync(payload);
      await qc.invalidateQueries({ queryKey: payrollKeys.payrun(created.id, false) });
      setGenerateOpen(false);
      setPeriodKey("");
      toast.success("Payrun generated");
      router.push(`/payroll/payruns/${created.id}`);
    } catch (err) {
      toastApiError(err);
    }
  }

  function onOpenExisting() {
    const payrunId = parseUuidParam(openId);
    if (!payrunId) {
      toast.error("Enter a valid payrun UUID.");
      return;
    }
    router.push(`/payroll/payruns/${payrunId}`);
  }

  return (
    <ListRightPanelTemplate
      header={
        <PageHeader
          title="Payruns"
          subtitle="Generate a new branch payrun or open an existing payrun by UUID."
          actions={
            canGenerate ? (
              <Sheet open={generateOpen} onOpenChange={setGenerateOpen}>
                <SheetTrigger asChild>
                  <Button type="button">Generate payrun</Button>
                </SheetTrigger>
                <SheetContent className="border-border-subtle bg-surface-2 backdrop-blur-xl">
                  <SheetHeader>
                    <SheetTitle>Generate payrun</SheetTitle>
                    <SheetDescription>
                      Payrun generation uses the active branch scope and backend payroll totals. No optimistic totals are shown in the UI.
                    </SheetDescription>
                  </SheetHeader>
                  <div className="space-y-4 px-4">
                    <div className="space-y-1">
                      <Label htmlFor="payrun-calendar">Calendar</Label>
                      <select
                        id="payrun-calendar"
                        className={selectClassName}
                        value={calendarId ?? ""}
                        onChange={(event) => setCalendarId(parseUuidParam(event.target.value))}
                      >
                        <option value="">Select…</option>
                        {calendars.map((calendar) => (
                          <option key={calendar.id} value={calendar.id}>
                            {calendar.name} ({calendar.code})
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="space-y-1">
                      <Label htmlFor="payrun-year">Year</Label>
                      <Input
                        id="payrun-year"
                        type="number"
                        min={2000}
                        max={2100}
                        value={year}
                        onChange={(event) => setYear(Number(event.target.value) || currentPayrollYear())}
                      />
                    </div>
                    <div className="space-y-1">
                      <Label htmlFor="payrun-period">Period</Label>
                      <select
                        id="payrun-period"
                        className={selectClassName}
                        value={periodKey}
                        onChange={(event) => setPeriodKey(event.target.value)}
                        disabled={!calendarId || periodsQ.isLoading}
                      >
                        <option value="">Select…</option>
                        {periods.map((period) => (
                          <option key={period.id} value={period.period_key}>
                            {period.period_key} ({period.start_date} to {period.end_date})
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-3 text-sm text-text-2">
                      Branch scope: {branchId}
                    </div>
                  </div>
                  <SheetFooter>
                    <Button
                      type="button"
                      disabled={generateM.isPending || !calendarId || !periodKey}
                      onClick={() => void onGenerate()}
                    >
                      {generateM.isPending ? "Generating..." : "Generate payrun"}
                    </Button>
                  </SheetFooter>
                </SheetContent>
              </Sheet>
            ) : null
          }
        />
      }
      main={
        <div className="space-y-6">
          <DSCard surface="card" className="space-y-4 p-[var(--ds-space-20)]">
            <div>
              <div className="text-sm font-semibold tracking-tight text-text-1">Generate from setup prerequisites</div>
              <div className="mt-1 text-sm text-text-2">
                Payroll v1 does not expose a payrun browse endpoint. Use this console to generate a payrun or open one directly if you already have its UUID.
              </div>
            </div>
            {calendarsQ.isLoading ? (
              <div className="text-sm text-text-2">Loading calendars…</div>
            ) : calendarsQ.error ? (
              <ErrorState
                title="Could not load calendars"
                error={calendarsQ.error}
                onRetry={() => void calendarsQ.refetch()}
                variant="inline"
                className="max-w-none"
              />
            ) : calendars.length === 0 ? (
              <EmptyState
                title="No payroll calendars"
                description="Create a payroll calendar and at least one period before generating a payrun."
                primaryAction={
                  <Button asChild variant="secondary">
                    <Link href="/payroll/calendars">Go to calendars</Link>
                  </Button>
                }
              />
            ) : (
              <div className="grid gap-4 md:grid-cols-2">
                <div className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-4">
                  <div className="text-xs text-text-2">Selected calendar</div>
                  <div className="mt-1 text-sm font-medium text-text-1">
                    {calendars.find((calendar) => calendar.id === calendarId)?.name ?? "Choose a calendar"}
                  </div>
                </div>
                <div className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-4">
                  <div className="text-xs text-text-2">Available periods</div>
                  <div className="mt-1 text-sm font-medium text-text-1">{periods.length}</div>
                </div>
              </div>
            )}
          </DSCard>

          <DSCard surface="card" className="space-y-4 p-[var(--ds-space-20)]">
            <div>
              <div className="text-sm font-semibold tracking-tight text-text-1">Open existing payrun</div>
              <div className="mt-1 text-sm text-text-2">
                Generated payruns have a canonical detail route. Use a payrun UUID to open one directly.
              </div>
            </div>
            <div className="space-y-1">
              <Label htmlFor="open-payrun-id">Payrun UUID</Label>
              <Input
                id="open-payrun-id"
                value={openId}
                onChange={(event) => setOpenId(event.target.value)}
                placeholder="xxxxxxxx-xxxx-4xxx-8xxx-xxxxxxxxxxxx"
              />
            </div>
            <div>
              <Button type="button" variant="secondary" onClick={onOpenExisting}>
                Open payrun
              </Button>
            </div>
          </DSCard>
        </div>
      }
      right={
        <RightPanelStack>
          <DSCard surface="panel" className="space-y-3 p-[var(--ds-space-16)]">
            <div className="text-sm font-semibold tracking-tight text-text-1">Current scope</div>
            <div className="text-sm text-text-2">Company: {companyId}</div>
            <div className="text-sm text-text-2">Branch: {branchId}</div>
          </DSCard>

          <DSCard surface="panel" className="space-y-3 p-[var(--ds-space-16)]">
            <div className="text-sm font-semibold tracking-tight text-text-1">Next step after generate</div>
            <div className="text-sm text-text-2">
              Review the payrun detail, submit it for approval, approve it in Workflow, then publish and export it.
            </div>
          </DSCard>
        </RightPanelStack>
      }
    />
  );
}
