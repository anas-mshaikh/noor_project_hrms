"use client";

/**
 * components/DailyInsights.tsx
 *
 * Lightweight, job-scoped dashboard built from AttendanceOut rows.
 * No extra API calls and no chart library required.
 */

import { useMemo, useState } from "react";
import type { AttendanceOut } from "@/lib/types";

const DEFAULT_LATE_AFTER = "10:30";

type Summary = {
  totalEmployees: number;
  present: number;
  absent: number;
  late: number;
  avgWorkedMinutes: number | null;
  avgPunchInMinutes: number | null;
  punchInMinutesSorted: number[];
};

function parseTimeToMinutes(value: string): number | null {
  // Parses "HH:MM" into minutes since midnight; returns null for invalid input.
  const parts = value.split(":");
  if (parts.length !== 2) return null;

  const hours = Number(parts[0]);
  const minutes = Number(parts[1]);

  if (!Number.isFinite(hours) || !Number.isFinite(minutes)) return null;
  if (hours < 0 || hours > 23 || minutes < 0 || minutes > 59) return null;

  return hours * 60 + minutes;
}

function minutesFromIso(dt: string): number {
  // Converts an ISO timestamp to local minutes since midnight.
  const d = new Date(dt);
  return d.getHours() * 60 + d.getMinutes();
}

function formatMinutes(minutes: number | null): string {
  if (minutes === null) return "—";
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

function isAbsent(row: AttendanceOut): boolean {
  // Absent is encoded in anomalies_json by the backend.
  const a = row.anomalies_json as { absent?: boolean } | null;
  return Boolean(a?.absent);
}

function PunchInTrend({ minutes }: { minutes: number[] }) {
  if (minutes.length < 2) {
    return (
      <div className="text-sm text-gray-600">
        Not enough punch‑ins to draw a trend yet.
      </div>
    );
  }

  const min = Math.min(...minutes);
  const max = Math.max(...minutes);
  const range = Math.max(1, max - min);

  const width = 420;
  const height = 120;
  const pad = 16;

  // Map time -> chart coordinates (top = earlier, bottom = later).
  const points = minutes.map((m, i) => {
    const x = pad + (i / Math.max(1, minutes.length - 1)) * (width - pad * 2);
    const y = pad + (1 - (m - min) / range) * (height - pad * 2);
    return [x, y] as const;
  });

  const path = points
    .map(
      (p, i) => `${i === 0 ? "M" : "L"}${p[0].toFixed(1)},${p[1].toFixed(1)}`
    )
    .join(" ");

  return (
    <div>
      <div className="mb-2 text-xs text-muted-foreground">
        Earliest: {formatMinutes(min)} • Latest: {formatMinutes(max)}
      </div>
      <svg
        width={width}
        height={height}
        className="w-full rounded-lg border bg-background"
        role="img"
        aria-label="Punch-in time trend"
      >
        <path d={path} fill="none" stroke="#2563eb" strokeWidth={2} />
        {points.map(([x, y], i) => (
          <circle key={i} cx={x} cy={y} r={2.5} fill="#2563eb" />
        ))}
      </svg>
    </div>
  );
}

export function DailyInsights({ rows }: { rows: AttendanceOut[] }) {
  const [lateAfter, setLateAfter] = useState(DEFAULT_LATE_AFTER);

  const lateAfterMinutes = useMemo(
    () => parseTimeToMinutes(lateAfter),
    [lateAfter]
  );

  const summary = useMemo<Summary>(() => {
    const totalEmployees = rows.length;
    const presentRows = rows.filter((r) => !isAbsent(r));
    const absent = totalEmployees - presentRows.length;

    const punchIns = presentRows
      .map((r) => (r.punch_in ? minutesFromIso(r.punch_in) : null))
      .filter((m): m is number => m !== null);

    const punchInMinutesSorted = [...punchIns].sort((a, b) => a - b);

    const totalWorked = presentRows.reduce(
      (sum, r) => sum + (r.total_minutes ?? 0),
      0
    );

    const avgWorkedMinutes =
      presentRows.length > 0
        ? Math.round(totalWorked / presentRows.length)
        : null;

    const avgPunchInMinutes =
      punchIns.length > 0
        ? Math.round(punchIns.reduce((a, b) => a + b, 0) / punchIns.length)
        : null;

    const late =
      lateAfterMinutes === null
        ? 0
        : presentRows.filter(
            (r) =>
              r.punch_in !== null &&
              minutesFromIso(r.punch_in) > lateAfterMinutes
          ).length;

    return {
      totalEmployees,
      present: presentRows.length,
      absent,
      late,
      avgWorkedMinutes,
      avgPunchInMinutes,
      punchInMinutesSorted,
    };
  }, [rows, lateAfterMinutes]);

  const presentPct =
    summary.totalEmployees > 0
      ? Math.round((summary.present / summary.totalEmployees) * 100)
      : 0;

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-lg border bg-muted/30 p-3">
          <div className="text-xs uppercase text-muted-foreground">Present</div>
          <div className="text-2xl font-semibold">{summary.present}</div>
          <div className="mt-2 h-2 w-full rounded bg-muted">
            <div
              className="h-2 rounded bg-green-600"
              style={{ width: `${presentPct}%` }}
            />
          </div>
          <div className="mt-1 text-xs text-muted-foreground">
            {presentPct}% of {summary.totalEmployees}
          </div>
        </div>

        <div className="rounded-lg border bg-muted/30 p-3">
          <div className="text-xs uppercase text-muted-foreground">Absent</div>
          <div className="text-2xl font-semibold">{summary.absent}</div>
          <div className="mt-1 text-xs text-muted-foreground">
            Based on anomalies_json.absent
          </div>
        </div>

        <div className="rounded-lg border bg-muted/30 p-3">
          <div className="text-xs uppercase text-muted-foreground">Avg Worked</div>
          <div className="text-2xl font-semibold">
            {summary.avgWorkedMinutes ?? "—"}
          </div>
          <div className="mt-1 text-xs text-muted-foreground">minutes</div>
        </div>

        <div className="rounded-lg border bg-muted/30 p-3">
          <div className="text-xs uppercase text-muted-foreground">Late Arrivals</div>
          <div className="text-2xl font-semibold">{summary.late}</div>
          <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
            <span>Late after</span>
            <input
              className="rounded-md border border-input bg-background px-2 py-1 text-xs"
              type="time"
              value={lateAfter}
              onChange={(e) => setLateAfter(e.target.value)}
            />
          </div>
          {lateAfterMinutes === null && (
            <div className="mt-1 text-xs text-destructive">Invalid time value</div>
          )}
        </div>
      </div>

      <div className="rounded-lg border bg-muted/30 p-3">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <div className="text-sm font-medium">Punch‑in Time Trend</div>
          <div className="text-xs text-muted-foreground">
            Avg: {formatMinutes(summary.avgPunchInMinutes)}
          </div>
        </div>
        <PunchInTrend minutes={summary.punchInMinutesSorted} />
      </div>
    </div>
  );
}
