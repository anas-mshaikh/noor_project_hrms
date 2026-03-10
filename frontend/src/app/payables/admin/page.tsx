"use client";

import * as React from "react";
import { toast } from "sonner";
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/lib/auth";
import { monthRangeLocal } from "@/lib/dateRange";
import { parseUuidParam } from "@/lib/guards";
import { useSelection } from "@/lib/selection";
import { toastApiError } from "@/lib/toastApiError";
import type { EmployeeDirectoryRowOut, PayableDaySummaryOut, UUID } from "@/lib/types";
import { listEmployees } from "@/features/hr-core/api/hrCore";
import { hrCoreKeys } from "@/features/hr-core/queryKeys";
import { getAdminPayableDays, recomputePayableDays } from "@/features/payables/api/payables";
import { payablesKeys } from "@/features/payables/queryKeys";
import { validatePayablesRange } from "@/features/payables/range";
import { BranchScopeState } from "@/features/roster/components";

import { DataTable } from "@/components/ds/DataTable";
import { DSCard } from "@/components/ds/DSCard";
import { EmptyState } from "@/components/ds/EmptyState";
import { ErrorState } from "@/components/ds/ErrorState";
import { FilterBar } from "@/components/ds/FilterBar";
import { PageHeader } from "@/components/ds/PageHeader";
import { RightPanelStack } from "@/components/ds/RightPanelStack";
import { StatusChip } from "@/components/ds/StatusChip";
import { ListRightPanelTemplate } from "@/components/ds/templates/ListRightPanelTemplate";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const LIMIT = 50;

export default function PayablesAdminPage() {
  const permissions = useAuth((s) => s.permissions);
  const permSet = React.useMemo(() => new Set(permissions ?? []), [permissions]);
  const canRead = permSet.has("attendance:payable:admin:read");
  const canRecompute = permSet.has("attendance:payable:recompute");

  const companyId = parseUuidParam(useSelection((s) => s.companyId));
  const branchId = parseUuidParam(useSelection((s) => s.branchId));
  const qc = useQueryClient();

  const month = React.useMemo(() => monthRangeLocal(new Date()), []);
  const [from, setFrom] = React.useState(month.from);
  const [to, setTo] = React.useState(month.to);
  const [employeeSearch, setEmployeeSearch] = React.useState("");
  const [employeeId, setEmployeeId] = React.useState<UUID | null>(null);
  const rangeError = validatePayablesRange({ from, to, maxDays: 366 });

  const employeesQ = useQuery({
    queryKey: hrCoreKeys.employees({
      companyId,
      q: employeeSearch.trim() ? employeeSearch.trim() : null,
      status: null,
      branchId,
      orgUnitId: null,
      limit: 8,
      offset: 0,
    }),
    enabled: Boolean(companyId && branchId && canRead),
    queryFn: () =>
      listEmployees({
        companyId: companyId as UUID,
        branchId: branchId as UUID,
        q: employeeSearch.trim() ? employeeSearch.trim() : null,
        limit: 8,
        offset: 0,
      }),
  });

  const payablesQ = useInfiniteQuery({
    queryKey: payablesKeys.admin({ from, to, branchId, employeeId, limit: LIMIT }),
    enabled: Boolean(branchId && canRead && !rangeError),
    queryFn: ({ pageParam }) =>
      getAdminPayableDays({
        from,
        to,
        branchId: branchId as UUID,
        employeeId,
        limit: LIMIT,
        cursor: (pageParam as string | null) ?? null,
      }),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  });

  const rows = React.useMemo(
    () => payablesQ.data?.pages.flatMap((page) => page.items ?? []) ?? [],
    [payablesQ.data],
  ) as PayableDaySummaryOut[];
  const employees = (employeesQ.data?.items ?? []) as EmployeeDirectoryRowOut[];
  const selected = rows[0] ?? null;

  const recomputeM = useMutation({
    mutationFn: async () => {
      if (!branchId) throw new Error("Select a branch first.");
      return recomputePayableDays({
        from,
        to,
        branch_id: branchId,
        employee_ids: employeeId ? [employeeId] : [],
      });
    },
    onSuccess: async (out) => {
      await qc.invalidateQueries({ queryKey: ["payables"] });
      toast.success(`Recomputed ${out.computed_rows} row${out.computed_rows === 1 ? "" : "s"}`);
    },
    onError: (err) => toastApiError(err),
  });

  if (!canRead) {
    return <ErrorState title="Access denied" error={new Error("Your account does not have access to admin payable summaries.")} />;
  }

  if (!companyId || !branchId) {
    return <BranchScopeState title="Select company and branch" description="Admin payable summaries are limited to the active branch scope." />;
  }

  return (
    <ListRightPanelTemplate
      header={
        <PageHeader
          title="Payables Admin"
          subtitle="Branch-scoped payroll input summaries and recompute controls."
          actions={
            canRecompute ? (
              <Button type="button" onClick={() => void recomputeM.mutateAsync()} disabled={recomputeM.isPending || Boolean(rangeError)}>
                {recomputeM.isPending ? "Recomputing..." : "Recompute"}
              </Button>
            ) : null
          }
        />
      }
      main={
        <DataTable
          toolbar={
            <FilterBar
              search={{
                value: employeeSearch,
                onChange: setEmployeeSearch,
                placeholder: "Search employees...",
                disabled: employeesQ.isLoading,
              }}
              dateRangeSlot={
                <div className="flex items-center gap-2">
                  <Input aria-label="From" type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
                  <Input aria-label="To" type="date" value={to} onChange={(e) => setTo(e.target.value)} />
                </div>
              }
              chips={
                <select
                  aria-label="Employee filter"
                  className="h-9 rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm"
                  value={employeeId ?? ""}
                  onChange={(e) => setEmployeeId(parseUuidParam(e.target.value))}
                >
                  <option value="">All employees</option>
                  {employees.map((employee) => (
                    <option key={employee.employee_id} value={employee.employee_id}>{employee.full_name}</option>
                  ))}
                </select>
              }
              onClearAll={employeeSearch || employeeId ? () => {
                setEmployeeSearch("");
                setEmployeeId(null);
              } : undefined}
            />
          }
          isLoading={payablesQ.isLoading || employeesQ.isLoading}
          error={rangeError ? new Error(rangeError) : payablesQ.error ?? employeesQ.error}
          onRetry={() => {
            void Promise.all([payablesQ.refetch(), employeesQ.refetch()]);
          }}
          isEmpty={!rangeError && !payablesQ.isLoading && !payablesQ.error && rows.length === 0}
          emptyState={<EmptyState title="No payable rows" description="No payable summaries were found for this branch and range." align="center" />}
          skeleton={{ rows: 8, cols: 7 }}
        >
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Day</TableHead>
                <TableHead>Employee</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Expected</TableHead>
                <TableHead>Worked</TableHead>
                <TableHead>Payable</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((row) => (
                <TableRow key={`${row.day}-${row.employee_id}`}>
                  <TableCell>{row.day}</TableCell>
                  <TableCell>{row.employee_id}</TableCell>
                  <TableCell>{row.day_type}</TableCell>
                  <TableCell><StatusChip status={row.presence_status} /></TableCell>
                  <TableCell>{row.expected_minutes}</TableCell>
                  <TableCell>{row.worked_minutes}</TableCell>
                  <TableCell>{row.payable_minutes}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {payablesQ.hasNextPage ? (
            <div className="mt-4 flex justify-end">
              <Button type="button" variant="secondary" onClick={() => void payablesQ.fetchNextPage()} disabled={payablesQ.isFetchingNextPage}>
                {payablesQ.isFetchingNextPage ? "Loading..." : "Load more"}
              </Button>
            </div>
          ) : null}
        </DataTable>
      }
      right={
        <RightPanelStack>
          <DSCard surface="panel" className="space-y-3 p-[var(--ds-space-16)]">
            <div className="text-sm font-medium text-text-1">Scope</div>
            <div className="text-sm text-text-2">Branch {branchId}</div>
            <div className="text-sm text-text-2">Range {from} to {to}</div>
          </DSCard>
          {selected ? (
            <DSCard surface="panel" className="space-y-3 p-[var(--ds-space-16)]">
              <div className="text-sm font-medium text-text-1">Latest row</div>
              <div className="text-sm text-text-1">{selected.day}</div>
              <div className="text-xs text-text-3">Employee {selected.employee_id}</div>
              <div className="text-xs text-text-3">Computed at {selected.computed_at ? new Date(selected.computed_at).toLocaleString() : "-"}</div>
            </DSCard>
          ) : (
            <DSCard surface="panel" className="p-[var(--ds-space-16)]">
              <EmptyState title="No detail" description="Fetch payable rows to inspect summary details." align="center" />
            </DSCard>
          )}
        </RightPanelStack>
      }
    />
  );
}
