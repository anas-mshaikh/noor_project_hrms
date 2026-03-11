"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/lib/auth";
import { monthRangeLocal } from "@/lib/dateRange";
import { parseUuidParam } from "@/lib/guards";
import { useSelection } from "@/lib/selection";
import { toastApiError } from "@/lib/toastApiError";
import type { EmployeeDirectoryRowOut, RosterOverrideOut, ShiftTemplateOut, UUID } from "@/lib/types";
import { getEmployee, listEmployees } from "@/features/hr-core/api/hrCore";
import { hrCoreKeys } from "@/features/hr-core/queryKeys";
import { listShiftTemplates, listEmployeeOverrides, upsertEmployeeOverride } from "@/features/roster/api/roster";
import { BranchScopeState, EmployeePickerCard } from "@/features/roster/components";
import { buildOverridePayload } from "@/features/roster/forms";
import { rosterKeys } from "@/features/roster/queryKeys";
import { validatePayablesRange } from "@/features/payables/range";

import { DataTable } from "@/components/ds/DataTable";
import { DSCard } from "@/components/ds/DSCard";
import { EmptyState } from "@/components/ds/EmptyState";
import { ErrorState } from "@/components/ds/ErrorState";
import { FilterBar } from "@/components/ds/FilterBar";
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
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const OVERRIDE_TYPES = ["SHIFT_CHANGE", "WEEKOFF", "WORKDAY"] as const;

type OverrideType = (typeof OVERRIDE_TYPES)[number] | "";

export default function RosterOverridesPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const permissions = useAuth((s) => s.permissions);
  const permSet = React.useMemo(() => new Set(permissions ?? []), [permissions]);
  const canRead = permSet.has("roster:override:read");
  const canWrite = permSet.has("roster:override:write");

  const companyId = parseUuidParam(useSelection((s) => s.companyId));
  const branchId = parseUuidParam(useSelection((s) => s.branchId));
  const employeeId = parseUuidParam(searchParams.get("employeeId"));
  const qc = useQueryClient();

  const month = React.useMemo(() => monthRangeLocal(new Date()), []);
  const [from, setFrom] = React.useState(month.from);
  const [to, setTo] = React.useState(month.to);
  const rangeError = validatePayablesRange({ from, to, maxDays: 31 });

  const [employeeSearch, setEmployeeSearch] = React.useState("");
  const employeePickerQ = useQuery({
    queryKey: hrCoreKeys.employees({
      companyId,
      q: employeeSearch.trim() ? employeeSearch.trim() : null,
      status: null,
      branchId,
      orgUnitId: null,
      limit: 12,
      offset: 0,
    }),
    enabled: Boolean(companyId && branchId && canRead),
    queryFn: () =>
      listEmployees({
        companyId: companyId as UUID,
        branchId: branchId as UUID,
        q: employeeSearch.trim() ? employeeSearch.trim() : null,
        limit: 12,
        offset: 0,
      }),
  });

  const employeeQ = useQuery({
    queryKey: hrCoreKeys.employee({ companyId, employeeId }),
    enabled: Boolean(companyId && employeeId && canRead),
    queryFn: () => getEmployee({ companyId, employeeId: employeeId as UUID }),
  });

  const shiftsQ = useQuery({
    queryKey: rosterKeys.shifts({ branchId, activeOnly: true }),
    enabled: Boolean(branchId && canRead),
    queryFn: () => listShiftTemplates({ branchId: branchId as UUID, activeOnly: true }),
  });

  const overridesQ = useQuery({
    queryKey: rosterKeys.overrides({ employeeId, from, to }),
    enabled: Boolean(employeeId && canRead && !rangeError),
    queryFn: () => listEmployeeOverrides({ employeeId: employeeId as UUID, from, to }),
  });

  const employees = React.useMemo(
    () => (employeePickerQ.data?.items ?? []) as EmployeeDirectoryRowOut[],
    [employeePickerQ.data],
  );
  const shifts = React.useMemo(
    () => (shiftsQ.data ?? []) as ShiftTemplateOut[],
    [shiftsQ.data],
  );
  const overrides = React.useMemo(
    () => (overridesQ.data ?? []) as RosterOverrideOut[],
    [overridesQ.data],
  );

  const [selectedId, setSelectedId] = React.useState<string | null>(null);
  const selected = React.useMemo(
    () => (selectedId ? overrides.find((row) => row.id === selectedId) ?? null : overrides[0] ?? null),
    [overrides, selectedId],
  );

  React.useEffect(() => {
    if (!selectedId && overrides[0]) setSelectedId(overrides[0].id);
  }, [overrides, selectedId]);

  function setEmployee(nextEmployeeId: UUID) {
    router.push(`/roster/overrides?employeeId=${nextEmployeeId}`);
  }

  const [sheetOpen, setSheetOpen] = React.useState(false);
  const [day, setDay] = React.useState(from);
  const [overrideType, setOverrideType] = React.useState<OverrideType>("SHIFT_CHANGE");
  const [shiftTemplateId, setShiftTemplateId] = React.useState("");
  const [notes, setNotes] = React.useState("");

  React.useEffect(() => {
    if (!sheetOpen) return;
    if (!shiftTemplateId && shifts[0]) setShiftTemplateId(shifts[0].id);
  }, [sheetOpen, shiftTemplateId, shifts]);

  const upsertM = useMutation({
    mutationFn: async ({
      nextEmployeeId,
      nextDay,
      payload,
    }: {
      nextEmployeeId: UUID;
      nextDay: string;
      payload: ReturnType<typeof buildOverridePayload>;
    }) => {
      return upsertEmployeeOverride({
        employeeId: nextEmployeeId,
        day: nextDay,
        payload,
      });
    },
    onSuccess: async () => {
      setSheetOpen(false);
      setNotes("");
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["roster", "overrides"] }),
        qc.invalidateQueries({ queryKey: ["payables"] }),
      ]);
      toast.success("Override saved");
    },
    onError: (err) => toastApiError(err),
  });

  function onSaveOverride() {
    if (!employeeId) {
      toastApiError(new Error("Select an employee first."));
      return;
    }
    if (!day) {
      toastApiError(new Error("Select a day first."));
      return;
    }

    try {
      const payload = buildOverridePayload({
        overrideType,
        shiftTemplateId: parseUuidParam(shiftTemplateId),
        notes,
      });
      upsertM.mutate({
        nextEmployeeId: employeeId,
        nextDay: day,
        payload,
      });
    } catch (err) {
      toastApiError(err);
    }
  }

  if (!canRead) {
    return <ErrorState title="Access denied" error={new Error("Your account does not have access to roster overrides.")} />;
  }

  if (!companyId || !branchId) {
    return <BranchScopeState title="Select company and branch" description="Overrides are managed inside the active company and branch scope." />;
  }

  if (!employeeId) {
    return (
      <div className="space-y-6">
        <PageHeader title="Overrides" subtitle="Choose an employee to manage day-specific roster overrides." />
        <EmployeePickerCard
          employees={employees}
          isLoading={employeePickerQ.isLoading}
          error={employeePickerQ.error}
          onRetry={employeePickerQ.refetch}
          search={employeeSearch}
          onSearch={setEmployeeSearch}
          onSelect={setEmployee}
        />
      </div>
    );
  }

  const currentEmployee = employeeQ.data;

  return (
    <ListRightPanelTemplate
      header={
        <PageHeader
          title="Overrides"
          subtitle={currentEmployee ? `${currentEmployee.person.first_name} ${currentEmployee.person.last_name}` : "Per-day roster overrides."}
          actions={
            canWrite ? (
              <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
                <SheetTrigger asChild>
                  <Button type="button">Create override</Button>
                </SheetTrigger>
                <SheetContent className="border-border-subtle bg-surface-2 backdrop-blur-xl">
                  <SheetHeader>
                    <SheetTitle>Create override</SheetTitle>
                    <SheetDescription>Overrides take precedence over assignments and branch defaults for the selected day.</SheetDescription>
                  </SheetHeader>
                  <div className="space-y-4 px-4 text-sm">
                    <div className="space-y-1">
                      <Label htmlFor="override-day">Day</Label>
                      <Input id="override-day" type="date" value={day} onChange={(e) => setDay(e.target.value)} disabled={upsertM.isPending} />
                    </div>
                    <div className="space-y-1">
                      <Label htmlFor="override-type">Override type</Label>
                      <select
                        id="override-type"
                        className="h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm"
                        value={overrideType}
                        onChange={(e) => setOverrideType(e.target.value as OverrideType)}
                        disabled={upsertM.isPending}
                      >
                        <option value="">Select...</option>
                        {OVERRIDE_TYPES.map((value) => (
                          <option key={value} value={value}>{value}</option>
                        ))}
                      </select>
                    </div>
                    <div className="space-y-1">
                      <Label htmlFor="override-shift">Shift template</Label>
                      <select
                        id="override-shift"
                        className="h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm"
                        value={shiftTemplateId}
                        onChange={(e) => setShiftTemplateId(e.target.value)}
                        disabled={overrideType !== "SHIFT_CHANGE" || upsertM.isPending}
                      >
                        <option value="">Select...</option>
                        {shifts.map((shift) => (
                          <option key={shift.id} value={shift.id}>{shift.code} - {shift.name}</option>
                        ))}
                      </select>
                    </div>
                    <div className="space-y-1">
                      <Label htmlFor="override-notes">Notes (optional)</Label>
                      <textarea
                        id="override-notes"
                        className="min-h-24 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm"
                        value={notes}
                        onChange={(e) => setNotes(e.target.value)}
                        disabled={upsertM.isPending}
                      />
                    </div>
                  </div>
                  <SheetFooter>
                    <Button type="button" variant="secondary" onClick={() => setSheetOpen(false)} disabled={upsertM.isPending}>Cancel</Button>
                    <Button type="button" onClick={onSaveOverride} disabled={upsertM.isPending}>{upsertM.isPending ? "Saving..." : "Save override"}</Button>
                  </SheetFooter>
                </SheetContent>
              </Sheet>
            ) : null
          }
        />
      }
      main={
        <DataTable
          toolbar={
            <FilterBar
              dateRangeSlot={
                <div className="flex items-center gap-2">
                  <Input aria-label="From" type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
                  <Input aria-label="To" type="date" value={to} onChange={(e) => setTo(e.target.value)} />
                </div>
              }
            />
          }
          isLoading={overridesQ.isLoading || employeeQ.isLoading || shiftsQ.isLoading}
          error={rangeError ? new Error(rangeError) : overridesQ.error ?? employeeQ.error ?? shiftsQ.error}
          onRetry={() => {
            void Promise.all([overridesQ.refetch(), employeeQ.refetch(), shiftsQ.refetch()]);
          }}
          isEmpty={!rangeError && !overridesQ.isLoading && !overridesQ.error && overrides.length === 0}
          emptyState={
            <EmptyState
              title="No overrides"
              description="No overrides were found for this employee and range."
              primaryAction={canWrite ? <Button type="button" onClick={() => setSheetOpen(true)}>Create override</Button> : undefined}
              align="center"
            />
          }
          skeleton={{ rows: 5, cols: 4 }}
        >
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Day</TableHead>
                <TableHead>Override type</TableHead>
                <TableHead>Shift</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {overrides.map((row) => {
                const shift = row.shift_template_id ? shifts.find((item) => item.id === row.shift_template_id) ?? null : null;
                return (
                  <TableRow
                    key={row.id}
                    data-state={selected?.id === row.id ? "selected" : undefined}
                    className="cursor-pointer"
                    onClick={() => setSelectedId(row.id)}
                  >
                    <TableCell>{row.day}</TableCell>
                    <TableCell>{row.override_type}</TableCell>
                    <TableCell>{shift ? `${shift.code} - ${shift.name}` : row.override_type === "SHIFT_CHANGE" ? row.shift_template_id : "-"}</TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </DataTable>
      }
      right={
        <RightPanelStack>
          <DSCard surface="panel" className="space-y-3 p-[var(--ds-space-16)]">
            <div className="text-sm font-medium text-text-1">Override precedence</div>
            <div className="text-sm text-text-2">Overrides supersede employee assignments and the branch default shift for the selected day.</div>
          </DSCard>

          {selected ? (
            <DSCard surface="panel" className="space-y-3 p-[var(--ds-space-16)]">
              <div className="text-sm font-medium text-text-1">Selected override</div>
              <div className="text-sm text-text-1">{selected.day}</div>
              <div className="text-sm text-text-2">{selected.override_type}</div>
              <div className="text-xs text-text-3">{selected.notes || "No notes"}</div>
            </DSCard>
          ) : (
            <DSCard surface="panel" className="p-[var(--ds-space-16)]">
              <EmptyState title="Select an override" description="Choose a row to inspect override details." align="center" />
            </DSCard>
          )}
        </RightPanelStack>
      }
    />
  );
}
