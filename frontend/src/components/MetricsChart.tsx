"use client";

/**
 * components/MetricsChart.tsx
 *
 * We’re not using a chart library yet (no extra deps),
 * so this is a simple “table + tiny bars” view.
 *
 * Data source:
 *   GET /api/v1/jobs/{job_id}/metrics/hourly
 */

import type { MetricsHourlyOut } from "@/lib/types";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

function fmtHour(dt: string): string {
  // Shows local time hour label.
  const d = new Date(dt);
  return d.toLocaleString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    day: "2-digit",
    month: "short",
  });
}

export function MetricsChart({ rows }: { rows: MetricsHourlyOut[] }) {
  if (rows.length === 0) {
    return <div className="text-sm text-muted-foreground">No hourly metrics.</div>;
  }

  const maxEntries = Math.max(...rows.map((r) => r.entries), 1);
  const maxExits = Math.max(...rows.map((r) => r.exits), 1);

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Hour</TableHead>
          <TableHead>Entries</TableHead>
          <TableHead>Exits</TableHead>
          <TableHead>Visitors</TableHead>
          <TableHead>Avg dwell (sec)</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((r) => {
          const entryPct = Math.round((r.entries / maxEntries) * 100);
          const exitPct = Math.round((r.exits / maxExits) * 100);

          return (
            <TableRow key={r.hour_start_ts}>
              <TableCell className="whitespace-nowrap">
                {fmtHour(r.hour_start_ts)}
              </TableCell>

              <TableCell>
                <div className="flex items-center gap-2">
                  <div className="w-12 text-right tabular-nums">{r.entries}</div>
                  <div className="h-2 w-32 rounded bg-muted">
                    <div
                      className="h-2 rounded bg-green-600"
                      style={{ width: `${entryPct}%` }}
                    />
                  </div>
                </div>
              </TableCell>

              <TableCell>
                <div className="flex items-center gap-2">
                  <div className="w-12 text-right tabular-nums">{r.exits}</div>
                  <div className="h-2 w-32 rounded bg-muted">
                    <div
                      className="h-2 rounded bg-blue-600"
                      style={{ width: `${exitPct}%` }}
                    />
                  </div>
                </div>
              </TableCell>

              <TableCell className="tabular-nums">{r.unique_visitors}</TableCell>
              <TableCell className="tabular-nums">
                {r.avg_dwell_sec === null ? "—" : r.avg_dwell_sec.toFixed(1)}
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
