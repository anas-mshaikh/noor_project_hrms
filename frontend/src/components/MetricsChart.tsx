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
    return <div className="text-sm text-gray-600">No hourly metrics.</div>;
  }

  const maxEntries = Math.max(...rows.map((r) => r.entries), 1);
  const maxExits = Math.max(...rows.map((r) => r.exits), 1);

  return (
    <div className="overflow-auto">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b">
            <th className="py-2 text-left">Hour</th>
            <th className="py-2 text-left">Entries</th>
            <th className="py-2 text-left">Exits</th>
            <th className="py-2 text-left">Visitors</th>
            <th className="py-2 text-left">Avg dwell (sec)</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const entryPct = Math.round((r.entries / maxEntries) * 100);
            const exitPct = Math.round((r.exits / maxExits) * 100);

            return (
              <tr key={r.hour_start_ts} className="border-b">
                <td className="py-2">{fmtHour(r.hour_start_ts)}</td>

                <td className="py-2">
                  <div className="flex items-center gap-2">
                    <div className="w-12 text-right tabular-nums">
                      {r.entries}
                    </div>
                    <div className="h-2 w-32 rounded bg-gray-200">
                      <div
                        className="h-2 rounded bg-green-600"
                        style={{ width: `${entryPct}%` }}
                      />
                    </div>
                  </div>
                </td>

                <td className="py-2">
                  <div className="flex items-center gap-2">
                    <div className="w-12 text-right tabular-nums">
                      {r.exits}
                    </div>
                    <div className="h-2 w-32 rounded bg-gray-200">
                      <div
                        className="h-2 rounded bg-blue-600"
                        style={{ width: `${exitPct}%` }}
                      />
                    </div>
                  </div>
                </td>

                <td className="py-2 tabular-nums">{r.unique_visitors}</td>
                <td className="py-2 tabular-nums">
                  {r.avg_dwell_sec === null ? "—" : r.avg_dwell_sec.toFixed(1)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
