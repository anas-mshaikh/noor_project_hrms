"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";

import { useAuth } from "@/lib/auth";
import type { AttendanceDayOut } from "@/lib/types";
import { listMyDays } from "@/features/attendance/api/attendance";
import { attendanceKeys } from "@/features/attendance/queryKeys";
import { addMonthsLocal, monthRangeLocal } from "@/lib/dateRange";

import { DataTable } from "@/components/ds/DataTable";
import { DSCard } from "@/components/ds/DSCard";
import { EmptyState } from "@/components/ds/EmptyState";
import { ErrorState } from "@/components/ds/ErrorState";
import { PageHeader } from "@/components/ds/PageHeader";
import { RightPanelStack } from "@/components/ds/RightPanelStack";
import { StatusChip } from "@/components/ds/StatusChip";
import { ListRightPanelTemplate } from "@/components/ds/templates/ListRightPanelTemplate";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

function formatMinutes(min: number): string {
  const m = Math.max(0, Number(min) || 0);
  const hh = Math.floor(m / 60);
  const mm = m % 60;
  return `${hh}h ${String(mm).padStart(2, "0")}m`;
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

export default function AttendanceDaysPage() {
  const user = useAuth((s) => s.user);
  const permissions = useAuth((s) => s.permissions);
  const permSet = React.useMemo(() => new Set(permissions ?? []), [permissions]);

  const canRead = permSet.has("attendance:correction:read");
  const canSubmit = permSet.has("attendance:correction:submit");

  const [month, setMonth] = React.useState(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  });

  const range = React.useMemo(() => monthRangeLocal(month), [month]);

  const daysQ = useQuery({
    queryKey: attendanceKeys.days({ from: range.from, to: range.to }),
    enabled: Boolean(user && canRead),
    queryFn: () => listMyDays({ from: range.from, to: range.to }),
  });

  const items = (daysQ.data?.items ?? []) as AttendanceDayOut[];

  const [selectedDay, setSelectedDay] = React.useState<string | null>(null);
  const selected = React.useMemo(
    () => (selectedDay ? items.find((i) => i.day === selectedDay) ?? null : null),
    [items, selectedDay]
  );

  React.useEffect(() => {
    // If month changes and the selected day is outside range, clear selection.
    if (!selectedDay) return;
    if (selectedDay < range.from || selectedDay > range.to) setSelectedDay(null);
  }, [selectedDay, range.from, range.to]);

  if (!user) {
    return (
      <ErrorState
        title="Sign in required"
        error={new Error("Please sign in to view your attendance days.")}
        details={
          <Button asChild variant="secondary">
            <Link href="/login">Sign in</Link>
          </Button>
        }
      />
    );
  }

  if (!canRead) {
    return (
      <ErrorState
        title="Access denied"
        error={new Error("Your account does not have access to attendance days.")}
      />
    );
  }

  return (
    <ListRightPanelTemplate
      header={
        <PageHeader
          title="Days"
          subtitle="Daily attendance status and minutes."
          actions={
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="secondary"
                onClick={() => setMonth((m) => addMonthsLocal(m, -1))}
              >
                Prev
              </Button>
              <Button
                type="button"
                variant="secondary"
                onClick={() => setMonth((m) => addMonthsLocal(m, 1))}
              >
                Next
              </Button>
              <Button asChild variant="outline">
                <Link href="/attendance/punch">Punch</Link>
              </Button>
            </div>
          }
        />
      }
      main={
        <DataTable
          isLoading={daysQ.isLoading}
          error={daysQ.error}
          onRetry={daysQ.refetch}
          isEmpty={!daysQ.isLoading && !daysQ.error && items.length === 0}
          emptyState={
            <EmptyState
              title="No days"
              description="No attendance days found for this range."
              align="center"
            />
          }
          skeleton={{ rows: 10, cols: 5 }}
        >
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Day</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Minutes</TableHead>
                <TableHead>First in</TableHead>
                <TableHead>Last out</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((d) => {
                const isSelected = selectedDay === d.day;
                return (
                  <TableRow
                    key={d.day}
                    className={isSelected ? "bg-surface-1" : undefined}
                  >
                    <TableCell className="font-medium">
                      <button
                        type="button"
                        className="hover:underline"
                        onClick={() => setSelectedDay(d.day)}
                      >
                        {d.day}
                      </button>
                    </TableCell>
                    <TableCell>
                      <StatusChip status={d.effective_status} />
                    </TableCell>
                    <TableCell className="text-text-2">
                      {formatMinutes(d.effective_minutes)}
                    </TableCell>
                    <TableCell className="text-text-2">{formatDateTime(d.first_in)}</TableCell>
                    <TableCell className="text-text-2">{formatDateTime(d.last_out)}</TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </DataTable>
      }
      right={
        <RightPanelStack>
          <DSCard surface="panel" className="p-[var(--ds-space-16)]">
            <div className="text-sm font-medium text-text-1">Range</div>
            <div className="mt-1 text-sm text-text-2">
              {range.from} to {range.to}
            </div>
          </DSCard>

          {daysQ.error ? (
            <DSCard surface="panel" className="p-[var(--ds-space-16)]">
              <ErrorState
                title="Could not load day details"
                error={daysQ.error}
                onRetry={daysQ.refetch}
                variant="inline"
                className="max-w-none"
              />
            </DSCard>
          ) : selected ? (
            <DSCard surface="panel" className="p-[var(--ds-space-16)]">
              <div className="flex items-start justify-between gap-3">
                <div className="space-y-1">
                  <div className="text-sm font-medium text-text-1">{selected.day}</div>
                  <div className="text-xs text-text-3">Base: {selected.base_status}</div>
                </div>
                <StatusChip status={selected.effective_status} />
              </div>

              <div className="mt-4 grid gap-3 text-sm">
                <div className="flex items-center justify-between gap-3">
                  <div className="text-text-2">Minutes (base)</div>
                  <div className="font-medium text-text-1">{formatMinutes(selected.base_minutes)}</div>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <div className="text-text-2">Minutes (effective)</div>
                  <div className="font-medium text-text-1">
                    {formatMinutes(selected.effective_minutes)}
                  </div>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <div className="text-text-2">First in</div>
                  <div className="font-medium text-text-1">{formatDateTime(selected.first_in)}</div>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <div className="text-text-2">Last out</div>
                  <div className="font-medium text-text-1">{formatDateTime(selected.last_out)}</div>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <div className="text-text-2">Open session</div>
                  <div className="font-medium text-text-1">
                    {selected.has_open_session ? "Yes" : "No"}
                  </div>
                </div>
              </div>

              <div className="mt-4 space-y-2 text-sm">
                <div className="text-xs font-medium text-text-2">Sources</div>
                {selected.sources?.length ? (
                  <div className="flex flex-wrap gap-2">
                    {selected.sources.map((s) => (
                      <div
                        key={s}
                        className="rounded-full border border-border-subtle bg-surface-1 px-3 py-1 text-xs text-text-2"
                      >
                        {s}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-sm text-text-3">—</div>
                )}
              </div>

              {selected.override ? (
                <div className="mt-4 space-y-2 text-sm">
                  <div className="text-xs font-medium text-text-2">Override</div>
                  <div className="text-sm text-text-1">
                    {selected.override.kind}: {selected.override.status}
                  </div>
                  <div className="text-xs text-text-3">
                    {selected.override.source_type} • {selected.override.source_id}
                  </div>
                </div>
              ) : null}

              <div className="mt-4 flex flex-wrap items-center gap-2">
                <Button asChild disabled={!canSubmit} variant="secondary">
                  <Link href={`/attendance/corrections/new?day=${encodeURIComponent(selected.day)}`}>
                    Request correction
                  </Link>
                </Button>
                {!canSubmit ? (
                  <div className="text-xs text-text-3">Requires attendance:correction:submit</div>
                ) : null}
              </div>
            </DSCard>
          ) : (
            <DSCard surface="panel" className="p-[var(--ds-space-16)]">
              <EmptyState
                title="Select a day"
                description="Pick a day from the list to see details."
                align="center"
              />
            </DSCard>
          )}
        </RightPanelStack>
      }
    />
  );
}
