"use client";

/**
 * components/AttendanceTable.tsx
 *
 * Renders attendance rows from:
 *   GET /api/v1/jobs/{job_id}/attendance
 *
 * The backend intentionally returns ALL employees for the store/day:
 * - present employees have punch_in/punch_out
 * - absent employees have punch_in/punch_out = null and anomalies_json={"absent": true}
 */

import type { AttendanceOut } from "@/lib/types";

function fmtDateTime(dt: string | null): string {
  if (!dt) return "—";
  return new Date(dt).toLocaleString();
}

function summarizeAnomalies(a: Record<string, unknown>): string[] {
  /**
   * anomalies_json is JSONB and can contain booleans or structured values.
   * For MVP we show keys that are “truthy”.
   */
  const entries = Object.entries(a ?? {});
  return entries
    .filter(([, v]) => Boolean(v))
    .map(([k]) => k)
    .slice(0, 10); // avoid huge UIs if anomalies grow later
}

export function AttendanceTable({ rows }: { rows: AttendanceOut[] }) {
  if (rows.length === 0) {
    return <div className="text-sm text-gray-600">No attendance rows.</div>;
  }

  return (
    <div className="overflow-auto">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b">
            <th className="py-2 text-left">Code</th>
            <th className="py-2 text-left">Name</th>
            <th className="py-2 text-left">Punch in</th>
            <th className="py-2 text-left">Punch out</th>
            <th className="py-2 text-left">Total (min)</th>
            <th className="py-2 text-left">Anomalies</th>
          </tr>
        </thead>

        <tbody>
          {rows.map((r) => {
            const anomalies = summarizeAnomalies(r.anomalies_json ?? {});
            const absent = Boolean((r.anomalies_json as any)?.absent);

            return (
              <tr
                key={r.employee_id}
                className={`border-b ${absent ? "bg-yellow-50" : ""}`}
              >
                <td className="py-2">{r.employee_code}</td>
                <td className="py-2">{r.employee_name}</td>
                <td className="py-2">{fmtDateTime(r.punch_in)}</td>
                <td className="py-2">{fmtDateTime(r.punch_out)}</td>
                <td className="py-2">
                  {r.total_minutes === null ? "—" : r.total_minutes}
                </td>
                <td className="py-2">
                  {anomalies.length === 0 ? (
                    <span className="text-gray-500">—</span>
                  ) : (
                    <div className="flex flex-wrap gap-1">
                      {anomalies.map((k) => (
                        <span
                          key={k}
                          className="rounded bg-gray-100 px-2 py-0.5 text-xs"
                        >
                          {k}
                        </span>
                      ))}
                    </div>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
