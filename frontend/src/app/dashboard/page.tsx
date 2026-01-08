"use client";

/**
 * /dashboard
 *
 * Store-scoped, date-range dashboard using:
 *   GET /api/v1/stores/{store_id}/attendance/daily
 */

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { apiJson } from "@/lib/api";
import { useSelection } from "@/lib/selection";
import type { AttendanceDailySummaryOut } from "@/lib/types";

function toLocalDateInput(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function formatMinutes(minutes: number | null): string {
  if (minutes === null) return "—";
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
      <div className="text-sm text-gray-600">
        Not enough punch‑ins to draw a trend yet.
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
      <div className="mb-2 text-xs text-gray-500">
        Earliest: {formatMinutes(min)} • Latest: {formatMinutes(max)}
      </div>
      <svg
        width={width}
        height={height}
        className="w-full rounded border bg-white"
        role="img"
        aria-label="Punch-in time trend"
      >
        <path d={path} fill="none" stroke="#2563eb" strokeWidth={2} />
        {coords.map(([x, y], i) => (
          <circle key={i} cx={x} cy={y} r={2.5} fill="#2563eb" />
        ))}
      </svg>
    </div>
  );
}

function AttendanceBars({ rows }: { rows: AttendanceDailySummaryOut[] }) {
  if (rows.length === 0) {
    return <div className="text-sm text-gray-600">No daily data yet.</div>;
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
            <div className="w-24 text-xs text-gray-500">{r.business_date}</div>
            <div className="flex h-3 w-56 overflow-hidden rounded bg-gray-200">
              <div
                className="bg-green-600"
                style={{ width: `${presentPct}%` }}
              />
              <div className="bg-red-500" style={{ width: `${absentPct}%` }} />
            </div>
            <div className="w-24 text-xs text-gray-600">
              {r.present_count}/{r.total_employees}
            </div>
            <div className="w-24 text-xs text-gray-600">
              late: {r.late_count}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function DashboardPage() {
  const storeId = useSelection((s) => s.storeId);

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
    queryKey: ["attendance-daily", storeId, startDate, endDate, lateAfter],
    enabled: Boolean(storeId && startDate && endDate && !dateError),
    queryFn: () => {
      if (!storeId) throw new Error("Missing storeId");
      const params = new URLSearchParams({
        start: startDate,
        end: endDate,
      });
      if (lateAfter) params.set("late_after", lateAfter);
      return apiJson<AttendanceDailySummaryOut[]>(
        `/api/v1/stores/${storeId}/attendance/daily?${params.toString()}`
      );
    },
  });

  const rows = dailyQ.data ?? [];

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
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-semibold">Dashboard</h1>
      </div>

      <section className="rounded border bg-white p-4">
        <div className="flex flex-wrap items-end gap-3 text-sm">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-500">Start date</label>
            <input
              className="rounded border px-2 py-1"
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
            />
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-500">End date</label>
            <input
              className="rounded border px-2 py-1"
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
            />
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-500">Late after</label>
            <input
              className="rounded border px-2 py-1"
              type="time"
              value={lateAfter}
              onChange={(e) => setLateAfter(e.target.value)}
            />
          </div>

          <button
            className="rounded border px-3 py-2 hover:bg-gray-50"
            onClick={() => dailyQ.refetch()}
            disabled={!storeId || Boolean(dateError)}
          >
            Refresh
          </button>
        </div>

        {!storeId && (
          <div className="mt-3 text-sm text-gray-600">
            Select a store to view the dashboard.
          </div>
        )}

        {dateError && (
          <div className="mt-3 text-sm text-red-600">{dateError}</div>
        )}
      </section>

      {storeId && !dateError && (
        <>
          <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded border bg-white p-3">
              <div className="text-xs uppercase text-gray-500">Avg Present</div>
              <div className="text-2xl font-semibold">{summary.presentAvg}</div>
              <div className="text-xs text-gray-500">per day</div>
            </div>

            <div className="rounded border bg-white p-3">
              <div className="text-xs uppercase text-gray-500">Avg Absent</div>
              <div className="text-2xl font-semibold">{summary.absentAvg}</div>
              <div className="text-xs text-gray-500">per day</div>
            </div>

            <div className="rounded border bg-white p-3">
              <div className="text-xs uppercase text-gray-500">Avg Late</div>
              <div className="text-2xl font-semibold">{summary.lateAvg}</div>
              <div className="text-xs text-gray-500">per day</div>
            </div>

            <div className="rounded border bg-white p-3">
              <div className="text-xs uppercase text-gray-500">Avg Worked</div>
              <div className="text-2xl font-semibold">
                {summary.avgWorkedMinutes ?? "—"}
              </div>
              <div className="text-xs text-gray-500">minutes</div>
            </div>
          </section>

          <section className="rounded border bg-white p-4">
            <h2 className="text-lg font-medium">Month Attendance (Daily)</h2>
            {dailyQ.isLoading ? (
              <div className="mt-2 text-sm text-gray-600">Loading…</div>
            ) : dailyQ.isError ? (
              <div className="mt-2 text-sm text-red-600">
                {String(dailyQ.error)}
              </div>
            ) : (
              <div className="mt-3">
                <AttendanceBars rows={rows} />
              </div>
            )}
          </section>

          <section className="rounded border bg-white p-4">
            <div className="mb-2 flex items-center justify-between">
              <h2 className="text-lg font-medium">Punch‑in Time Trend</h2>
              <div className="text-xs text-gray-500">
                Avg: {formatMinutes(summary.avgPunchInMinutes)}
              </div>
            </div>
            <PunchInTrend rows={rows} />
          </section>

          <section className="rounded border bg-white p-4">
            <h2 className="text-lg font-medium">Daily Table</h2>
            {rows.length === 0 ? (
              <div className="mt-2 text-sm text-gray-600">No data yet.</div>
            ) : (
              <div className="mt-3 overflow-auto">
                <table className="w-full border-collapse text-sm">
                  <thead>
                    <tr className="border-b">
                      <th className="py-2 text-left">Date</th>
                      <th className="py-2 text-left">Present</th>
                      <th className="py-2 text-left">Absent</th>
                      <th className="py-2 text-left">Late</th>
                      <th className="py-2 text-left">Avg Worked</th>
                      <th className="py-2 text-left">Avg Punch‑in</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r) => (
                      <tr key={r.business_date} className="border-b">
                        <td className="py-2">{r.business_date}</td>
                        <td className="py-2">{r.present_count}</td>
                        <td className="py-2">{r.absent_count}</td>
                        <td className="py-2">{r.late_count}</td>
                        <td className="py-2">
                          {r.avg_worked_minutes === null
                            ? "—"
                            : Math.round(r.avg_worked_minutes)}
                        </td>
                        <td className="py-2">
                          {formatMinutes(r.avg_punch_in_minutes)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
