"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/lib/auth";
import { parseUuidParam } from "@/lib/guards";
import { useSelection } from "@/lib/selection";
import { toastApiError } from "@/lib/toastApiError";
import type { EmployeeDirectoryRowOut, ShiftAssignmentOut, ShiftTemplateOut, UUID } from "@/lib/types";
import { listEmployees, getEmployee } from "@/features/hr-core/api/hrCore";
import { hrCoreKeys } from "@/features/hr-core/queryKeys";
import { createEmployeeAssignment, listEmployeeAssignments, listShiftTemplates } from "@/features/roster/api/roster";
import { EmployeePickerCard, BranchScopeState } from "@/features/roster/components";
import { buildAssignmentPayload } from "@/features/roster/forms";
import { rosterKeys } from "@/features/roster/queryKeys";

import { DataTable } from "@/components/ds/DataTable";
import { DSCard } from "@/components/ds/DSCard";
import { EmptyState } from "@/components/ds/EmptyState";
import { ErrorState } from "@/components/ds/ErrorState";
import { PageHeader } from "@/components/ds/PageHeader";
import { RightPanelStack } from "@/components/ds/RightPanelStack";
import { StatusChip } from "@/components/ds/StatusChip";
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

function formatDate(value: string | null | undefined): string {
  return value || "-";
}

export default function RosterAssignmentsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const permissions = useAuth((s) => s.permissions);
  const permSet = React.useMemo(() => new Set(permissions ?? []), [permissions]);
  const canRead = permSet.has("roster:assignment:read");
  const canWrite = permSet.has("roster:assignment:write");

  const companyId = parseUuidParam(useSelection((s) => s.companyId));
  const branchId = parseUuidParam(useSelection((s) => s.branchId));
  const employeeId = parseUuidParam(searchParams.get("employeeId"));
  const qc = useQueryClient();

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

  const assignmentsQ = useQuery({
    queryKey: rosterKeys.assignments(employeeId),
    enabled: Boolean(employeeId && canRead),
    queryFn: () => listEmployeeAssignments(employeeId as UUID),
  });

  const assignments = React.useMemo(
    () => (assignmentsQ.data ?? []) as ShiftAssignmentOut[],
    [assignmentsQ.data],
  );
  const shifts = React.useMemo(
    () => (shiftsQ.data ?? []) as ShiftTemplateOut[],
    [shiftsQ.data],
  );
  const employees = React.useMemo(
    () => (employeePickerQ.data?.items ?? []) as EmployeeDirectoryRowOut[],
    [employeePickerQ.data],
  );

  const [selectedId, setSelectedId] = React.useState<string | null>(null);
  const selected = React.useMemo(
    () => (selectedId ? assignments.find((row) => row.id === selectedId) ?? null : assignments[0] ?? null),
    [assignments, selectedId],
  );

  React.useEffect(() => {
    if (!selectedId && assignments[0]) setSelectedId(assignments[0].id);
  }, [assignments, selectedId]);

  function setEmployee(nextEmployeeId: UUID) {
    router.push(`/roster/assignments?employeeId=${nextEmployeeId}`);
  }

  const [sheetOpen, setSheetOpen] = React.useState(false);
  const [shiftTemplateId, setShiftTemplateId] = React.useState("");
  const [effectiveFrom, setEffectiveFrom] = React.useState("");
  const [effectiveTo, setEffectiveTo] = React.useState("");

  React.useEffect(() => {
    if (!sheetOpen) return;
    if (!shiftTemplateId && shifts[0]) setShiftTemplateId(shifts[0].id);
  }, [sheetOpen, shiftTemplateId, shifts]);

  const createM = useMutation({
    mutationFn: async () => {
      if (!employeeId) throw new Error("Select an employee first.");
      return createEmployeeAssignment(
        employeeId,
        buildAssignmentPayload({
          shiftTemplateId: parseUuidParam(shiftTemplateId),
          effectiveFrom,
          effectiveTo,
        }),
      );
    },
    onSuccess: async () => {
      setSheetOpen(false);
      setEffectiveFrom("");
      setEffectiveTo("");
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["roster", "assignments"] }),
        qc.invalidateQueries({ queryKey: ["payables"] }),
      ]);
      toast.success("Assignment created");
    },
    onError: (err) => toastApiError(err),
  });

  if (!canRead) {
    return <ErrorState title="Access denied" error={new Error("Your account does not have access to roster assignments.")} />;
  }

  if (!companyId || !branchId) {
    return <BranchScopeState title="Select company and branch" description="Assignments are created within the active company and branch scope." />;
  }

  if (!employeeId) {
    return (
      <div className="space-y-6">
        <PageHeader title="Shift Assignments" subtitle="Choose an employee to manage effective-dated shift assignments." />
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
  const selectedShift = selected ? shifts.find((shift) => shift.id === selected.shift_template_id) ?? null : null;

  return (
    <ListRightPanelTemplate
      header={
        <PageHeader
          title="Shift Assignments"
          subtitle={currentEmployee ? `${currentEmployee.person.first_name} ${currentEmployee.person.last_name}` : "Employee shift assignments."}
          actions={
            canWrite ? (
              <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
                <SheetTrigger asChild>
                  <Button type="button">Create assignment</Button>
                </SheetTrigger>
                <SheetContent className="border-border-subtle bg-surface-2 backdrop-blur-xl">
                  <SheetHeader>
                    <SheetTitle>Create assignment</SheetTitle>
                    <SheetDescription>Assign a shift template for an effective date range.</SheetDescription>
                  </SheetHeader>
                  <div className="space-y-4 px-4 text-sm">
                    <div className="space-y-1">
                      <Label htmlFor="assignment-shift">Shift template</Label>
                      <select
                        id="assignment-shift"
                        className="h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm"
                        value={shiftTemplateId}
                        onChange={(e) => setShiftTemplateId(e.target.value)}
                        disabled={createM.isPending}
                      >
                        <option value="">Select...</option>
                        {shifts.map((shift) => (
                          <option key={shift.id} value={shift.id}>{shift.code} - {shift.name}</option>
                        ))}
                      </select>
                    </div>
                    <div className="grid gap-4 sm:grid-cols-2">
                      <div className="space-y-1"><Label htmlFor="assignment-from">Effective from</Label><Input id="assignment-from" type="date" value={effectiveFrom} onChange={(e) => setEffectiveFrom(e.target.value)} disabled={createM.isPending} /></div>
                      <div className="space-y-1"><Label htmlFor="assignment-to">Effective to (optional)</Label><Input id="assignment-to" type="date" value={effectiveTo} onChange={(e) => setEffectiveTo(e.target.value)} disabled={createM.isPending} /></div>
                    </div>
                  </div>
                  <SheetFooter>
                    <Button type="button" variant="secondary" onClick={() => setSheetOpen(false)} disabled={createM.isPending}>Cancel</Button>
                    <Button type="button" onClick={() => void createM.mutateAsync()} disabled={createM.isPending}>{createM.isPending ? "Saving..." : "Create assignment"}</Button>
                  </SheetFooter>
                </SheetContent>
              </Sheet>
            ) : null
          }
        />
      }
      main={
        <DataTable
          isLoading={assignmentsQ.isLoading || employeeQ.isLoading || shiftsQ.isLoading}
          error={assignmentsQ.error ?? employeeQ.error ?? shiftsQ.error}
          onRetry={() => {
            void Promise.all([assignmentsQ.refetch(), employeeQ.refetch(), shiftsQ.refetch()]);
          }}
          isEmpty={!assignmentsQ.isLoading && !assignmentsQ.error && assignments.length === 0}
          emptyState={
            <EmptyState
              title="No assignments"
              description="Create the first assignment for this employee."
              primaryAction={canWrite ? <Button type="button" onClick={() => setSheetOpen(true)}>Create assignment</Button> : undefined}
              align="center"
            />
          }
          skeleton={{ rows: 5, cols: 4 }}
        >
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Shift</TableHead>
                <TableHead>Effective from</TableHead>
                <TableHead>Effective to</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {assignments.map((assignment) => {
                const shift = shifts.find((row) => row.id === assignment.shift_template_id) ?? null;
                return (
                  <TableRow
                    key={assignment.id}
                    data-state={selected?.id === assignment.id ? "selected" : undefined}
                    className="cursor-pointer"
                    onClick={() => setSelectedId(assignment.id)}
                  >
                    <TableCell>
                      <div className="font-medium text-text-1">{shift?.name ?? assignment.shift_template_id}</div>
                      <div className="text-xs text-text-3">{shift?.code ?? "Unknown shift"}</div>
                    </TableCell>
                    <TableCell>{assignment.effective_from}</TableCell>
                    <TableCell>{assignment.effective_to ?? "Open-ended"}</TableCell>
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
            <div className="text-sm font-medium text-text-1">Employee</div>
            {currentEmployee ? (
              <>
                <div className="text-sm text-text-1">{currentEmployee.person.first_name} {currentEmployee.person.last_name}</div>
                <div className="text-xs text-text-3">{currentEmployee.employee.employee_code}</div>
                <StatusChip status={currentEmployee.employee.status} />
              </>
            ) : (
              <div className="text-sm text-text-3">Loading employee…</div>
            )}
          </DSCard>

          {selected ? (
            <DSCard surface="panel" className="space-y-3 p-[var(--ds-space-16)]">
              <div className="text-sm font-medium text-text-1">Selected assignment</div>
              <div className="text-sm text-text-1">{selectedShift?.name ?? selected.shift_template_id}</div>
              <div className="text-xs text-text-3">{selectedShift?.code ?? "Unknown shift"}</div>
              <div className="grid gap-3 text-sm sm:grid-cols-2">
                <div>
                  <div className="text-xs text-text-3">Effective from</div>
                  <div className="font-medium text-text-1">{formatDate(selected.effective_from)}</div>
                </div>
                <div>
                  <div className="text-xs text-text-3">Effective to</div>
                  <div className="font-medium text-text-1">{formatDate(selected.effective_to)}</div>
                </div>
              </div>
            </DSCard>
          ) : (
            <DSCard surface="panel" className="p-[var(--ds-space-16)]">
              <EmptyState title="Select an assignment" description="Choose a row to see assignment details." align="center" />
            </DSCard>
          )}
        </RightPanelStack>
      }
    />
  );
}
