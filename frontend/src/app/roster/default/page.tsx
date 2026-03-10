"use client";

import * as React from "react";
import Link from "next/link";
import { toast } from "sonner";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { parseUuidParam } from "@/lib/guards";
import { useSelection } from "@/lib/selection";
import { toastApiError } from "@/lib/toastApiError";
import type { ShiftTemplateOut, UUID } from "@/lib/types";
import { getBranchDefaultShift, listShiftTemplates, setBranchDefaultShift } from "@/features/roster/api/roster";
import { rosterKeys } from "@/features/roster/queryKeys";
import { BranchScopeState } from "@/features/roster/components";

import { DSCard } from "@/components/ds/DSCard";
import { EmptyState } from "@/components/ds/EmptyState";
import { ErrorState } from "@/components/ds/ErrorState";
import { PageHeader } from "@/components/ds/PageHeader";
import { ListRightPanelTemplate } from "@/components/ds/templates/ListRightPanelTemplate";
import { Button } from "@/components/ui/button";
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

function timeValue(value: string): string {
  return value.slice(0, 5);
}

export default function RosterDefaultPage() {
  const permissions = useAuth((s) => s.permissions);
  const permSet = React.useMemo(() => new Set(permissions ?? []), [permissions]);
  const canRead = permSet.has("roster:shift:read");
  const canWrite = permSet.has("roster:defaults:write");

  const branchId = parseUuidParam(useSelection((s) => s.branchId));
  const qc = useQueryClient();

  const shiftsQ = useQuery({
    queryKey: rosterKeys.shifts({ branchId, activeOnly: false }),
    enabled: Boolean(branchId && canRead),
    queryFn: () => listShiftTemplates({ branchId: branchId as UUID, activeOnly: false }),
  });

  const defaultQ = useQuery({
    queryKey: rosterKeys.defaultShift(branchId),
    enabled: Boolean(branchId && canRead),
    retry: false,
    queryFn: () => getBranchDefaultShift(branchId as UUID),
  });

  const shifts = React.useMemo(
    () => (shiftsQ.data ?? []) as ShiftTemplateOut[],
    [shiftsQ.data],
  );
  const currentShift = React.useMemo(() => {
    const defaultShiftId = defaultQ.data?.default_shift_template_id ?? null;
    return shifts.find((shift) => shift.id === defaultShiftId) ?? null;
  }, [defaultQ.data, shifts]);

  const [sheetOpen, setSheetOpen] = React.useState(false);
  const [selectedShiftId, setSelectedShiftId] = React.useState<string>("");

  React.useEffect(() => {
    if (currentShift) setSelectedShiftId(currentShift.id);
    else if (shifts[0]) setSelectedShiftId(shifts[0].id);
  }, [currentShift, shifts]);

  const updateM = useMutation({
    mutationFn: async () => {
      if (!branchId) throw new Error("Select a branch first.");
      if (!selectedShiftId) throw new Error("Select a shift template first.");
      return setBranchDefaultShift(branchId, { shift_template_id: selectedShiftId as UUID });
    },
    onSuccess: async () => {
      setSheetOpen(false);
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["roster", "default-shift"] }),
        qc.invalidateQueries({ queryKey: ["payables"] }),
      ]);
      toast.success("Default shift updated");
    },
    onError: (err) => toastApiError(err),
  });

  if (!canRead) {
    return <ErrorState title="Access denied" error={new Error("Your account does not have access to branch default shifts.")} />;
  }

  if (!branchId) {
    return <BranchScopeState title="Select a branch" description="Default shifts are configured per branch. Select a branch to continue." />;
  }

  if (shiftsQ.error) {
    return <ErrorState title="Could not load shifts" error={shiftsQ.error} onRetry={shiftsQ.refetch} />;
  }

  if (!shiftsQ.isLoading && shifts.length === 0) {
    return (
      <EmptyState
        title="No shift templates"
        description="Create a shift template before setting a branch default."
        primaryAction={
          <Button asChild>
            <Link href="/roster/shifts">Create shift</Link>
          </Button>
        }
      />
    );
  }

  const defaultMissing = defaultQ.error instanceof ApiError && defaultQ.error.code === "roster.default.not_found";

  return (
    <ListRightPanelTemplate
      header={
        <PageHeader
          title="Default Shift"
          subtitle="Set the branch fallback shift used when no employee assignment exists."
          actions={
            canWrite ? (
              <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
                <SheetTrigger asChild>
                  <Button type="button">{defaultMissing ? "Set default shift" : "Update default shift"}</Button>
                </SheetTrigger>
                <SheetContent className="border-border-subtle bg-surface-2 backdrop-blur-xl">
                  <SheetHeader>
                    <SheetTitle>{defaultMissing ? "Set default shift" : "Update default shift"}</SheetTitle>
                    <SheetDescription>Select the fallback shift for this branch.</SheetDescription>
                  </SheetHeader>
                  <div className="space-y-4 px-4 text-sm">
                    <div className="space-y-1">
                      <Label htmlFor="default-shift">Shift template</Label>
                      <select
                        id="default-shift"
                        className="h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm"
                        value={selectedShiftId}
                        onChange={(e) => setSelectedShiftId(e.target.value)}
                        disabled={updateM.isPending}
                      >
                        <option value="">Select...</option>
                        {shifts.map((shift) => (
                          <option key={shift.id} value={shift.id}>
                            {shift.code} - {shift.name}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                  <SheetFooter>
                    <Button type="button" variant="secondary" onClick={() => setSheetOpen(false)} disabled={updateM.isPending}>Cancel</Button>
                    <Button type="button" onClick={() => void updateM.mutateAsync()} disabled={updateM.isPending}>{updateM.isPending ? "Saving..." : "Save default"}</Button>
                  </SheetFooter>
                </SheetContent>
              </Sheet>
            ) : null
          }
        />
      }
      main={
        defaultMissing ? (
          <DSCard surface="card" className="p-[var(--ds-space-20)]">
            <EmptyState
              title="No default shift set"
              description="Set a branch default shift so payable day computation has a fallback roster."
              primaryAction={canWrite ? <Button type="button" onClick={() => setSheetOpen(true)}>Set default shift</Button> : undefined}
            />
          </DSCard>
        ) : defaultQ.isLoading ? (
          <DSCard surface="card" className="p-[var(--ds-space-20)]">
            <div className="text-sm text-text-3">Loading...</div>
          </DSCard>
        ) : defaultQ.error ? (
          <ErrorState title="Could not load default shift" error={defaultQ.error} onRetry={defaultQ.refetch} />
        ) : currentShift ? (
          <DSCard surface="card" className="space-y-4 p-[var(--ds-space-20)]">
            <div>
              <div className="text-lg font-semibold text-text-1">{currentShift.name}</div>
              <div className="mt-1 text-sm text-text-2">{currentShift.code}</div>
            </div>
            <div className="grid gap-4 text-sm sm:grid-cols-2">
              <div>
                <div className="text-xs text-text-3">Shift hours</div>
                <div className="font-medium text-text-1">{timeValue(currentShift.start_time)} - {timeValue(currentShift.end_time)}</div>
              </div>
              <div>
                <div className="text-xs text-text-3">Expected minutes</div>
                <div className="font-medium text-text-1">{currentShift.expected_minutes}</div>
              </div>
            </div>
          </DSCard>
        ) : (
          <DSCard surface="card" className="p-[var(--ds-space-20)]">
            <EmptyState title="Default shift missing" description="The selected default shift is no longer available." />
          </DSCard>
        )
      }
      right={
        <DSCard surface="panel" className="space-y-3 p-[var(--ds-space-16)]">
          <div className="text-sm font-medium text-text-1">How it works</div>
          <div className="text-sm text-text-2">
            The branch default shift is used when an employee does not have an active assignment and no override exists for the day.
          </div>
        </DSCard>
      }
    />
  );
}
