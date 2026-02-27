"use client";

/**
 * /dashboard
 *
 * Branch-scoped, date-range dashboard using:
 *   GET /api/v1/branches/{branch_id}/attendance/daily
 */

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "@/lib/i18n";

import { apiJson } from "@/lib/api";
import { useSelection } from "@/lib/selection";
import type { AttendanceDailySummaryOut } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { DSCard } from "@/components/ds/DSCard";
import { PageHeader } from "@/components/ds/PageHeader";
import { RightPanelStack } from "@/components/ds/RightPanelStack";
import { ListRightPanelTemplate } from "@/components/ds/templates/ListRightPanelTemplate";

function toLocalDateInput(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function formatMinutes(minutes: number | null): string {
  if (minutes === null) return "-";
  const h = Math.floor(minutes / 60);
  const m = Math.round(minutes % 60);
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

function PunchInTrend({ rows }: { rows: AttendanceDailySummaryOut[] }) {
  const points = rows
    .map((r) => r.avg_punch_in_minutes)
    .filter((v): v is number => v !== null);

  if (points.length < 2) {
    return (
      <div className="text-sm text-muted-foreground">
        Not enough punch-ins to draw a trend yet.
      </div>
    );
  }

  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = Math.max(1, max - min);

  const width = 520;
  const height = 140;
  const pad = 16;

  const coords = points.map((m, i) => {
    const x = pad + (i / Math.max(1, points.length - 1)) * (width - pad * 2);
    const y = pad + (1 - (m - min) / range) * (height - pad * 2);
    return [x, y] as const;
  });

  const path = coords
    .map(
      (p, i) => `${i === 0 ? "M" : "L"}${p[0].toFixed(1)},${p[1].toFixed(1)}`
    )
    .join(" ");

  return (
    <div>
      <div className="mb-2 text-xs text-muted-foreground">
        Earliest: {formatMinutes(min)} | Latest: {formatMinutes(max)}
      </div>
      <svg
        width={width}
        height={height}
        className="w-full rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1"
        role="img"
        aria-label="Punch-in time trend"
      >
        <path d={path} fill="none" stroke="#a855f7" strokeWidth={2} />
        {coords.map(([x, y], i) => (
          <circle key={i} cx={x} cy={y} r={2.5} fill="#a855f7" />
        ))}
      </svg>
    </div>
  );
}

function AttendanceBars({ rows }: { rows: AttendanceDailySummaryOut[] }) {
  if (rows.length === 0) {
    return <div className="text-sm text-muted-foreground">No daily data yet.</div>;
  }

  return (
    <div className="space-y-2">
      {rows.map((r) => {
        const total = r.total_employees || 1;
        const presentPct = Math.round((r.present_count / total) * 100);
        const absentPct = Math.round((r.absent_count / total) * 100);

        return (
          <div
            key={r.business_date}
            className="flex items-center gap-3 text-sm"
          >
            <div className="w-24 text-xs text-muted-foreground">{r.business_date}</div>
            <div className="flex h-3 w-56 overflow-hidden rounded bg-muted">
              <div
                className="bg-green-600"
                style={{ width: `${presentPct}%` }}
              />
              <div className="bg-red-500" style={{ width: `${absentPct}%` }} />
            </div>
            <div className="w-24 text-xs text-muted-foreground">
              {r.present_count}/{r.total_employees}
            </div>
            <div className="w-24 text-xs text-muted-foreground">
              late: {r.late_count}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function DashboardPage() {
  const { t } = useTranslation();
  const branchId = useSelection((s) => s.branchId);

  const [endDate, setEndDate] = useState(() => toLocalDateInput(new Date()));
  const [startDate, setStartDate] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() - 29);
    return toLocalDateInput(d);
  });
  const [lateAfter, setLateAfter] = useState("10:30");

  const dateError = useMemo(() => {
    if (startDate && endDate && startDate > endDate) {
      return "Start date must be before end date.";
    }
    return null;
  }, [startDate, endDate]);

  const dailyQ = useQuery({
    queryKey: ["attendance-daily", branchId, startDate, endDate, lateAfter],
    enabled: Boolean(branchId && startDate && endDate && !dateError),
    queryFn: () => {
      if (!branchId) throw new Error("Missing branchId");
      const params = new URLSearchParams({
        start: startDate,
        end: endDate,
      });
      if (lateAfter) params.set("late_after", lateAfter);
      return apiJson<AttendanceDailySummaryOut[]>(
        `/api/v1/branches/${branchId}/attendance/daily?${params.toString()}`
      );
    },
  });

  const rows = useMemo(() => dailyQ.data ?? [], [dailyQ.data]);

  const summary = useMemo(() => {
    const totalDays = rows.length;
    const totalEmployees = rows[0]?.total_employees ?? 0;

    const presentSum = rows.reduce((s, r) => s + r.present_count, 0);
    const absentSum = rows.reduce((s, r) => s + r.absent_count, 0);
    const lateSum = rows.reduce((s, r) => s + r.late_count, 0);

    const avgWorked =
      rows
        .map((r) => r.avg_worked_minutes)
        .filter((v): v is number => v !== null)
        .reduce((s, v) => s + v, 0) /
      Math.max(1, rows.filter((r) => r.avg_worked_minutes !== null).length);

    const avgPunchIn =
      rows
        .map((r) => r.avg_punch_in_minutes)
        .filter((v): v is number => v !== null)
        .reduce((s, v) => s + v, 0) /
      Math.max(1, rows.filter((r) => r.avg_punch_in_minutes !== null).length);

    return {
      totalDays,
      totalEmployees,
      presentAvg: totalDays ? Math.round(presentSum / totalDays) : 0,
      absentAvg: totalDays ? Math.round(absentSum / totalDays) : 0,
      lateAvg: totalDays ? Math.round(lateSum / totalDays) : 0,
      avgWorkedMinutes: Number.isFinite(avgWorked)
        ? Math.round(avgWorked)
        : null,
      avgPunchInMinutes: Number.isFinite(avgPunchIn)
        ? Math.round(avgPunchIn)
        : null,
    };
  }, [rows]);

  return (
    <ListRightPanelTemplate
      header={
        <PageHeader
          title={t("nav.items.dashboard.title", { defaultValue: "Dashboard" })}
          subtitle={t("page.dashboard.subtitle", {
            defaultValue: "Branch-scoped attendance summary across a date range.",
          })}
          meta={
            branchId ? (
              <span className="rounded-full border border-border-subtle bg-surface-1 px-3 py-1 text-xs text-text-2">
                branch_id: {branchId}
              </span>
            ) : (
              <span className="rounded-full border border-border-subtle bg-surface-1 px-3 py-1 text-xs text-text-2">
                Select a branch to view metrics
              </span>
            )
          }
        />
      }
      main={
        <>
          <DSCard surface="card" className="p-[var(--ds-space-20)]">
            <div className="space-y-1">
              <div className="text-base font-semibold tracking-tight text-text-1">
                Filters
              </div>
              <div className="text-sm text-text-2">
                Pick a date range and a late-after cutoff.
              </div>
            </div>

            <div className="mt-4 space-y-3">
              <div className="grid gap-3 text-sm sm:grid-cols-4">
                <div className="space-y-1">
                  <Label className="text-xs text-text-2">Start date</Label>
                  <Input
                    type="date"
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                  />
                </div>

                <div className="space-y-1">
                  <Label className="text-xs text-text-2">End date</Label>
                  <Input
                    type="date"
                    value={endDate}
                    onChange={(e) => setEndDate(e.target.value)}
                  />
                </div>

                <div className="space-y-1">
                  <Label className="text-xs text-text-2">Late after</Label>
                  <Input
                    type="time"
                    value={lateAfter}
                    onChange={(e) => setLateAfter(e.target.value)}
                  />
                </div>

                <div className="flex items-end">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => dailyQ.refetch()}
                    disabled={!branchId || Boolean(dateError)}
                    className="border-border-subtle bg-surface-1 hover:bg-surface-2"
                  >
                    Refresh
                  </Button>
                </div>
              </div>

              {dateError ? (
                <div className="text-sm text-destructive">{dateError}</div>
              ) : null}
            </div>
          </DSCard>

          {branchId && !dateError ? (
            <>
              <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <DSCard surface="panel" className="p-[var(--ds-space-20)]">
                  <div className="text-xs uppercase text-text-2">Avg Present</div>
                  <div className="mt-2 text-2xl font-semibold text-text-1">
                    {summary.presentAvg}
                  </div>
                  <div className="text-xs text-text-2">per day</div>
                </DSCard>

                <DSCard surface="panel" className="p-[var(--ds-space-20)]">
                  <div className="text-xs uppercase text-text-2">Avg Absent</div>
                  <div className="mt-2 text-2xl font-semibold text-text-1">
                    {summary.absentAvg}
                  </div>
                  <div className="text-xs text-text-2">per day</div>
                </DSCard>

                <DSCard surface="panel" className="p-[var(--ds-space-20)]">
                  <div className="text-xs uppercase text-text-2">Avg Late</div>
                  <div className="mt-2 text-2xl font-semibold text-text-1">
                    {summary.lateAvg}
                  </div>
                  <div className="text-xs text-text-2">per day</div>
                </DSCard>

                <DSCard surface="panel" className="p-[var(--ds-space-20)]">
                  <div className="text-xs uppercase text-text-2">Avg Worked</div>
                  <div className="mt-2 text-2xl font-semibold text-text-1">
                    {summary.avgWorkedMinutes ?? "-"}
                  </div>
                  <div className="text-xs text-text-2">minutes</div>
                </DSCard>
              </section>

              <DSCard surface="card" className="p-[var(--ds-space-20)]">
                <div className="space-y-1">
                  <div className="text-base font-semibold tracking-tight text-text-1">
                    Month Attendance (Daily)
                  </div>
                  <div className="text-sm text-text-2">
                    Present/absent breakdown per day.
                  </div>
                </div>
                <div className="mt-4">
                  {dailyQ.isLoading ? (
                    <div className="text-sm text-text-2">Loading...</div>
                  ) : dailyQ.isError ? (
                    <div className="text-sm text-destructive">
                      {String(dailyQ.error)}
                    </div>
                  ) : (
                    <AttendanceBars rows={rows} />
                  )}
                </div>
              </DSCard>

              <DSCard surface="card" className="p-[var(--ds-space-20)]">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="text-base font-semibold tracking-tight text-text-1">
                    Punch-in Time Trend
                  </div>
                  <div className="text-xs text-text-2">
                    Avg: {formatMinutes(summary.avgPunchInMinutes)}
                  </div>
                </div>
                <div className="mt-4">
                  <PunchInTrend rows={rows} />
                </div>
              </DSCard>

              <DSCard surface="card" className="p-[var(--ds-space-20)]">
                <div className="text-base font-semibold tracking-tight text-text-1">
                  Daily Table
                </div>
                <div className="mt-4">
                  {rows.length === 0 ? (
                    <div className="text-sm text-text-2">No data yet.</div>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Date</TableHead>
                          <TableHead>Present</TableHead>
                          <TableHead>Absent</TableHead>
                          <TableHead>Late</TableHead>
                          <TableHead>Avg Worked</TableHead>
                          <TableHead>Avg Punch-in</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {rows.map((r) => (
                          <TableRow key={r.business_date}>
                            <TableCell className="whitespace-nowrap">
                              {r.business_date}
                            </TableCell>
                            <TableCell className="tabular-nums">
                              {r.present_count}
                            </TableCell>
                            <TableCell className="tabular-nums">
                              {r.absent_count}
                            </TableCell>
                            <TableCell className="tabular-nums">
                              {r.late_count}
                            </TableCell>
                            <TableCell className="tabular-nums">
                              {r.avg_worked_minutes === null
                                ? "-"
                                : Math.round(r.avg_worked_minutes)}
                            </TableCell>
                            <TableCell className="tabular-nums">
                              {formatMinutes(r.avg_punch_in_minutes)}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}
                </div>
              </DSCard>
            </>
          ) : null}
        </>
      }
      right={
        <RightPanelStack>
          <DSCard surface="panel" className="p-[var(--ds-space-20)]">
            <div className="text-sm font-medium text-text-1">Scope</div>
            <div className="mt-2 space-y-1 text-sm text-text-2">
              <div>
                <span className="text-text-3">branch_id</span>:{" "}
                <span className="font-mono text-xs">{branchId ?? "-"}</span>
              </div>
            </div>
            <div className="mt-3 text-xs text-text-3">
              Payroll/attendance are computed on branch timezone. Always verify you are
              looking at the correct branch.
            </div>
          </DSCard>

          <DSCard surface="panel" className="p-[var(--ds-space-20)]">
            <div className="text-sm font-medium text-text-1">Support</div>
            <div className="mt-2 text-sm text-text-2">
              If a metric looks wrong, check the date range and branch selection. When
              reporting issues, include the correlation id from the error banner.
            </div>
          </DSCard>
        </RightPanelStack>
      }
    />
  );
}
