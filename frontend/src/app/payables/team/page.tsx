"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";

import { useAuth } from "@/lib/auth";
import { monthRangeLocal } from "@/lib/dateRange";
import type { PayableDaySummaryOut } from "@/lib/types";
import { getTeamPayableDays } from "@/features/payables/api/payables";
import { payablesKeys } from "@/features/payables/queryKeys";
import { aggregateTeamPayables, validatePayablesRange } from "@/features/payables/range";

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
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

export default function PayablesTeamPage() {
  const user = useAuth((s) => s.user);
  const permissions = useAuth((s) => s.permissions);
  const permSet = React.useMemo(() => new Set(permissions ?? []), [permissions]);
  const canRead = permSet.has("attendance:payable:team:read");
  const canWorkflow = permSet.has("workflow:request:read") || permSet.has("workflow:request:admin");

  const month = React.useMemo(() => monthRangeLocal(new Date()), []);
  const [from, setFrom] = React.useState(month.from);
  const [to, setTo] = React.useState(month.to);
  const [depth, setDepth] = React.useState<"1" | "all">("1");
  const rangeError = validatePayablesRange({ from, to, maxDays: 62 });

  const payablesQ = useQuery({
    queryKey: payablesKeys.team({ from, to, depth }),
    enabled: Boolean(user && canRead && !rangeError),
    queryFn: () => getTeamPayableDays({ from, to, depth }),
  });

  const rows = React.useMemo(
    () => (payablesQ.data?.items ?? []) as PayableDaySummaryOut[],
    [payablesQ.data],
  );
  const summaries = React.useMemo(() => aggregateTeamPayables(rows), [rows]);
  const [selectedEmployeeId, setSelectedEmployeeId] = React.useState<string | null>(null);
  const selected = React.useMemo(
    () => (selectedEmployeeId ? summaries.find((row) => row.employeeId === selectedEmployeeId) ?? null : summaries[0] ?? null),
    [selectedEmployeeId, summaries],
  );

  if (!user) {
    return (
      <ErrorState
        title="Sign in required"
        error={new Error("Please sign in to view team payable day summaries.")}
        details={<Button asChild variant="secondary"><Link href="/login">Sign in</Link></Button>}
      />
    );
  }

  if (!canRead) {
    return <ErrorState title="Access denied" error={new Error("Your account does not have access to team payable summaries.")} />;
  }

  return (
    <ListRightPanelTemplate
      header={
        <PageHeader
          title="Team Payables"
          subtitle="Range summaries for your direct or indirect reports."
          actions={
            <div className="flex items-center gap-2">
              <Label htmlFor="team-depth" className="text-xs text-text-2">Depth</Label>
              <select
                id="team-depth"
                className="h-9 rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm"
                value={depth}
                onChange={(e) => setDepth(e.target.value as "1" | "all")}
              >
                <option value="1">Direct</option>
                <option value="all">All</option>
              </select>
            </div>
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
          isLoading={payablesQ.isLoading}
          error={rangeError ? new Error(rangeError) : payablesQ.error}
          onRetry={payablesQ.refetch}
          isEmpty={!rangeError && !payablesQ.isLoading && !payablesQ.error && summaries.length === 0}
          emptyState={<EmptyState title="No team payables" description="No payable summaries were returned for this range." align="center" />}
          skeleton={{ rows: 8, cols: 5 }}
        >
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Employee</TableHead>
                <TableHead>Days</TableHead>
                <TableHead>Present</TableHead>
                <TableHead>Absent</TableHead>
                <TableHead>Payable minutes</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {summaries.map((row) => (
                <TableRow
                  key={row.employeeId}
                  data-state={selected?.employeeId === row.employeeId ? "selected" : undefined}
                  className="cursor-pointer"
                  onClick={() => setSelectedEmployeeId(row.employeeId)}
                >
                  <TableCell>{row.employeeId}</TableCell>
                  <TableCell>{row.totalDays}</TableCell>
                  <TableCell>{row.presentDays}</TableCell>
                  <TableCell>{row.absentDays}</TableCell>
                  <TableCell>{row.payableMinutes}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </DataTable>
      }
      right={
        <RightPanelStack>
          <DSCard surface="panel" className="space-y-3 p-[var(--ds-space-16)]">
            <div className="text-sm font-medium text-text-1">Range</div>
            <div className="text-sm text-text-2">{from} to {to}</div>
            {canWorkflow ? (
              <Button asChild type="button" variant="secondary"><Link href="/workflow/inbox">Workflow Inbox</Link></Button>
            ) : null}
          </DSCard>
          {selected ? (
            <DSCard surface="panel" className="space-y-3 p-[var(--ds-space-16)]">
              <div className="text-sm font-medium text-text-1">Employee breakdown</div>
              <div className="text-sm text-text-1">{selected.employeeId}</div>
              <div className="space-y-2">
                {selected.rows.map((row) => (
                  <div key={row.day} className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 px-3 py-2 text-sm">
                    <div className="font-medium text-text-1">{row.day}</div>
                    <div className="text-xs text-text-3">{row.day_type} • {row.presence_status}</div>
                    <div className="text-xs text-text-3">Expected {row.expected_minutes} • Worked {row.worked_minutes} • Payable {row.payable_minutes}</div>
                  </div>
                ))}
              </div>
            </DSCard>
          ) : (
            <DSCard surface="panel" className="p-[var(--ds-space-16)]">
              <EmptyState title="Select an employee" description="Choose a row to inspect the daily breakdown." align="center" />
            </DSCard>
          )}
        </RightPanelStack>
      }
    />
  );
}
