"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";

import { useAuth } from "@/lib/auth";
import { addMonthsLocal, eachDayInclusiveLocal, monthRangeLocal, ymdFromDateLocal } from "@/lib/dateRange";
import { useSelection } from "@/lib/selection";
import type { TeamLeaveSpanOut } from "@/lib/types";
import { getTeamCalendar } from "@/features/leave/api/leave";
import { leaveKeys } from "@/features/leave/queryKeys";

import { CalendarTemplate } from "@/components/ds/templates/CalendarTemplate";
import { DSCard } from "@/components/ds/DSCard";
import { EmptyState } from "@/components/ds/EmptyState";
import { ErrorState } from "@/components/ds/ErrorState";
import { PageHeader } from "@/components/ds/PageHeader";
import { RightPanelStack } from "@/components/ds/RightPanelStack";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { StorePicker } from "@/components/StorePicker";

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

function spansByDay(spans: TeamLeaveSpanOut[], days: string[]): Map<string, TeamLeaveSpanOut[]> {
  const out = new Map<string, TeamLeaveSpanOut[]>();
  for (const d of days) out.set(d, []);

  // Small ranges only (month). O(n*m) is OK here.
  for (const s of spans) {
    for (const d of days) {
      if (d >= s.start_date && d <= s.end_date) {
        out.get(d)?.push(s);
      }
    }
  }
  return out;
}

function aggregateTypes(spans: TeamLeaveSpanOut[]): Array<{ code: string; count: number }> {
  const m = new Map<string, number>();
  for (const s of spans) m.set(s.leave_type_code, (m.get(s.leave_type_code) ?? 0) + 1);
  return Array.from(m.entries())
    .map(([code, count]) => ({ code, count }))
    .sort((a, b) => a.code.localeCompare(b.code));
}

export default function LeaveTeamCalendarPage() {
  const user = useAuth((s) => s.user);
  const permissions = useAuth((s) => s.permissions);
  const permSet = React.useMemo(() => new Set(permissions ?? []), [permissions]);

  const canRead = permSet.has("leave:team:read");

  const companyId = useSelection((s) => s.companyId);

  const [month, setMonth] = React.useState(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  });
  const range = React.useMemo(() => monthRangeLocal(month), [month]);

  const [depth, setDepth] = React.useState<"1" | "all">("1");

  const calQ = useQuery({
    queryKey: leaveKeys.teamCalendar({ from: range.from, to: range.to, depth, branchId: null }),
    enabled: Boolean(user && canRead && companyId),
    queryFn: () =>
      getTeamCalendar({
        from: range.from,
        to: range.to,
        depth,
        branchId: null,
      }),
  });

  const spans = (calQ.data?.items ?? []) as TeamLeaveSpanOut[];

  const dayDates = React.useMemo(() => eachDayInclusiveLocal(range.fromDate, range.toDate), [range.fromDate, range.toDate]);
  const dayYmds = React.useMemo(() => dayDates.map(ymdFromDateLocal), [dayDates]);

  const spansMap = React.useMemo(() => spansByDay(spans, dayYmds), [spans, dayYmds]);

  const [selectedDay, setSelectedDay] = React.useState<string | null>(null);
  const selectedSpans = selectedDay ? spansMap.get(selectedDay) ?? [] : [];

  if (!user) {
    return (
      <ErrorState
        title="Sign in required"
        error={new Error("Please sign in to view the team calendar.")}
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
        error={new Error("Your account does not have access to the team leave calendar.")}
      />
    );
  }

  if (!companyId) {
    return (
      <ErrorState
        title="Scope required"
        error={new Error("Select a company to view your team calendar.")}
        details={<StorePicker />}
      />
    );
  }

  const firstDow = range.fromDate.getDay(); // 0..6
  const totalCells = firstDow + dayDates.length;
  const rows = Math.ceil(totalCells / 7);
  const cells: Array<{ ymd: string | null }> = [];
  for (let i = 0; i < firstDow; i++) cells.push({ ymd: null });
  for (const d of dayYmds) cells.push({ ymd: d });
  while (cells.length < rows * 7) cells.push({ ymd: null });

  return (
    <CalendarTemplate
      header={
        <PageHeader
          title="Team Calendar"
          subtitle="Approved leave spans for your team."
          actions={
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-2">
                <Label htmlFor="team-cal-depth" className="text-xs text-text-2">
                  Depth
                </Label>
                <select
                  id="team-cal-depth"
                  className="h-9 rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm"
                  value={depth}
                  onChange={(e) => setDepth(e.target.value as "1" | "all")}
                  disabled={calQ.isLoading}
                >
                  <option value="1">Direct</option>
                  <option value="all">All</option>
                </select>
              </div>
              <Button type="button" variant="secondary" onClick={() => setMonth((m) => addMonthsLocal(m, -1))}>
                Prev
              </Button>
              <Button type="button" variant="secondary" onClick={() => setMonth((m) => addMonthsLocal(m, 1))}>
                Next
              </Button>
              <Button asChild variant="outline">
                <Link href="/workflow/inbox">Workflow</Link>
              </Button>
            </div>
          }
        />
      }
      calendar={
        <DSCard surface="card" className="p-[var(--ds-space-20)]">
          <div className="grid grid-cols-7 gap-2">
            {WEEKDAYS.map((w) => (
              <div key={w} className="px-2 py-1 text-xs font-medium text-text-2">
                {w}
              </div>
            ))}
            {cells.map((c, idx) => {
              if (!c.ymd) {
                return <div key={idx} className="min-h-20 rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1/30" />;
              }
              const dayNum = Number(c.ymd.slice(-2));
              const daySpans = spansMap.get(c.ymd) ?? [];
              const agg = aggregateTypes(daySpans);
              const isSelected = selectedDay === c.ymd;

              return (
                <button
                  key={c.ymd}
                  type="button"
                  onClick={() => setSelectedDay(c.ymd)}
                  className={[
                    "min-h-20 rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-2 text-left transition",
                    isSelected ? "ring-2 ring-ring" : "hover:bg-surface-1/80",
                  ].join(" ")}
                >
                  <div className="text-xs font-medium text-text-1">{dayNum}</div>
                  <div className="mt-2 space-y-1">
                    {agg.slice(0, 2).map((a) => (
                      <div
                        key={a.code}
                        className="inline-flex items-center rounded-full border border-border-subtle bg-background px-2 py-0.5 text-[11px] text-text-2"
                      >
                        {a.code} ({a.count})
                      </div>
                    ))}
                    {agg.length > 2 ? (
                      <div className="text-[11px] text-text-3">+{agg.length - 2} more</div>
                    ) : null}
                  </div>
                </button>
              );
            })}
          </div>

          {calQ.isLoading ? (
            <div className="mt-4 text-sm text-text-3">Loading…</div>
          ) : calQ.error ? (
            <div className="mt-4">
              <ErrorState
                title="Could not load calendar"
                error={calQ.error}
                onRetry={calQ.refetch}
                variant="inline"
                className="max-w-none"
              />
            </div>
          ) : spans.length === 0 ? (
            <div className="mt-4">
              <EmptyState
                title="No leaves"
                description="No approved leaves found for this range."
                align="center"
              />
            </div>
          ) : null}
        </DSCard>
      }
      right={
        <RightPanelStack>
          <DSCard surface="panel" className="p-[var(--ds-space-16)]">
            <div className="text-sm font-medium text-text-1">Range</div>
            <div className="mt-1 text-sm text-text-2">
              {range.from} to {range.to}
            </div>
          </DSCard>

          {selectedDay ? (
            <DSCard surface="panel" className="p-[var(--ds-space-16)]">
              <div className="text-sm font-medium text-text-1">{selectedDay}</div>
              <div className="mt-2 text-sm text-text-2">
                {selectedSpans.length ? `${selectedSpans.length} leave span(s)` : "No leaves"}
              </div>
              <div className="mt-3 space-y-2 text-sm">
                {selectedSpans.map((s) => (
                  <div
                    key={s.leave_request_id}
                    className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 px-3 py-2"
                  >
                    <div className="text-xs text-text-3">{s.employee_id}</div>
                    <div className="mt-1 font-medium text-text-1">{s.leave_type_code}</div>
                    <div className="text-xs text-text-3">
                      {s.start_date} → {s.end_date} • {s.requested_days}d
                    </div>
                  </div>
                ))}
              </div>
            </DSCard>
          ) : (
            <DSCard surface="panel" className="p-[var(--ds-space-16)]">
              <EmptyState
                title="Select a day"
                description="Pick a day to see leave details."
                align="center"
              />
            </DSCard>
          )}
        </RightPanelStack>
      }
    />
  );
}
