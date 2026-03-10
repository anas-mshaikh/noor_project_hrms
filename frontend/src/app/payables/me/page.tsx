"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";

import { useAuth } from "@/lib/auth";
import { monthRangeLocal } from "@/lib/dateRange";
import type { PayableDaySummaryOut } from "@/lib/types";
import { getMyPayableDays } from "@/features/payables/api/payables";
import { payablesKeys } from "@/features/payables/queryKeys";
import { validatePayablesRange } from "@/features/payables/range";

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

function summary(rows: PayableDaySummaryOut[]) {
  return {
    payableDays: rows.filter((row) => row.payable_minutes > 0).length,
    leaveDays: rows.filter((row) => row.day_type === "ON_LEAVE").length,
    absentDays: rows.filter((row) => row.presence_status === "ABSENT").length,
    payableMinutes: rows.reduce((sum, row) => sum + row.payable_minutes, 0),
    computedAt: rows.reduce((latest, row) => (row.computed_at > latest ? row.computed_at : latest), ""),
  };
}

export default function PayablesMePage() {
  const user = useAuth((s) => s.user);
  const permissions = useAuth((s) => s.permissions);
  const permSet = React.useMemo(() => new Set(permissions ?? []), [permissions]);
  const canRead = permSet.has("attendance:payable:read");

  const month = React.useMemo(() => monthRangeLocal(new Date()), []);
  const [from, setFrom] = React.useState(month.from);
  const [to, setTo] = React.useState(month.to);
  const rangeError = validatePayablesRange({ from, to, maxDays: 62 });

  const payablesQ = useQuery({
    queryKey: payablesKeys.me({ from, to }),
    enabled: Boolean(user && canRead && !rangeError),
    queryFn: () => getMyPayableDays({ from, to }),
  });

  const rows = React.useMemo(
    () => (payablesQ.data?.items ?? []) as PayableDaySummaryOut[],
    [payablesQ.data],
  );
  const [selectedDay, setSelectedDay] = React.useState<string | null>(null);
  const selected = React.useMemo(
    () => (selectedDay ? rows.find((row) => row.day === selectedDay) ?? null : rows[0] ?? null),
    [rows, selectedDay],
  );
  const totals = summary(rows);

  if (!user) {
    return (
      <ErrorState
        title="Sign in required"
        error={new Error("Please sign in to view payable day summaries.")}
        details={<Button asChild variant="secondary"><Link href="/login">Sign in</Link></Button>}
      />
    );
  }

  if (!canRead) {
    return <ErrorState title="Access denied" error={new Error("Your account does not have access to payable day summaries.")} />;
  }

  return (
    <ListRightPanelTemplate
      header={<PageHeader title="Payable Days" subtitle="Your roster-aware payable day summaries." />}
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
          isEmpty={!rangeError && !payablesQ.isLoading && !payablesQ.error && rows.length === 0}
          emptyState={<EmptyState title="No payable days" description="No payable summaries were returned for this range." align="center" />}
          skeleton={{ rows: 8, cols: 6 }}
        >
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Day</TableHead>
                <TableHead>Day type</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Expected</TableHead>
                <TableHead>Worked</TableHead>
                <TableHead>Payable</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((row) => (
                <TableRow
                  key={row.day}
                  data-state={selected?.day === row.day ? "selected" : undefined}
                  className="cursor-pointer"
                  onClick={() => setSelectedDay(row.day)}
                >
                  <TableCell>{row.day}</TableCell>
                  <TableCell>{row.day_type}</TableCell>
                  <TableCell><StatusChip status={row.presence_status} /></TableCell>
                  <TableCell>{row.expected_minutes}</TableCell>
                  <TableCell>{row.worked_minutes}</TableCell>
                  <TableCell>{row.payable_minutes}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </DataTable>
      }
      right={
        <RightPanelStack>
          <DSCard surface="panel" className="grid gap-3 p-[var(--ds-space-16)] text-sm sm:grid-cols-2">
            <div><div className="text-xs text-text-3">Payable days</div><div className="font-medium text-text-1">{totals.payableDays}</div></div>
            <div><div className="text-xs text-text-3">Leave days</div><div className="font-medium text-text-1">{totals.leaveDays}</div></div>
            <div><div className="text-xs text-text-3">Absent days</div><div className="font-medium text-text-1">{totals.absentDays}</div></div>
            <div><div className="text-xs text-text-3">Payable minutes</div><div className="font-medium text-text-1">{totals.payableMinutes}</div></div>
          </DSCard>
          {selected ? (
            <DSCard surface="panel" className="space-y-3 p-[var(--ds-space-16)]">
              <div className="text-sm font-medium text-text-1">Selected day</div>
              <div className="text-sm text-text-1">{selected.day}</div>
              <div className="flex flex-wrap gap-2">
                <StatusChip status={selected.presence_status} />
                <StatusChip status={selected.day_type} />
              </div>
              <div className="grid gap-3 text-sm sm:grid-cols-2">
                <div><div className="text-xs text-text-3">Expected</div><div className="font-medium text-text-1">{selected.expected_minutes}</div></div>
                <div><div className="text-xs text-text-3">Worked</div><div className="font-medium text-text-1">{selected.worked_minutes}</div></div>
                <div><div className="text-xs text-text-3">Payable</div><div className="font-medium text-text-1">{selected.payable_minutes}</div></div>
                <div><div className="text-xs text-text-3">Computed at</div><div className="font-medium text-text-1">{selected.computed_at ? new Date(selected.computed_at).toLocaleString() : "-"}</div></div>
              </div>
            </DSCard>
          ) : (
            <DSCard surface="panel" className="p-[var(--ds-space-16)]">
              <EmptyState title="Select a day" description="Choose a row to inspect a payable summary." align="center" />
            </DSCard>
          )}
        </RightPanelStack>
      }
    />
  );
}
