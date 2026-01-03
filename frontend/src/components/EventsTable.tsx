"use client";

/**
 * components/EventsTable.tsx
 *
 * Renders events from:
 *   GET /api/v1/jobs/{job_id}/events?limit=...
 *
 * We highlight inferred events because they are important edge-cases:
 * - first_seen_inside (inferred entry)
 * - track_ended_inside (inferred exit)
 */

import type { EventOut } from "@/lib/types";

function fmtDateTime(dt: string): string {
  return new Date(dt).toLocaleString();
}

export function EventsTable({ rows }: { rows: EventOut[] }) {
  if (rows.length === 0) {
    return <div className="text-sm text-gray-600">No events.</div>;
  }

  return (
    <div className="overflow-auto">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b">
            <th className="py-2 text-left">Time</th>
            <th className="py-2 text-left">Type</th>
            <th className="py-2 text-left">Employee</th>
            <th className="py-2 text-left">Track</th>
            <th className="py-2 text-left">Inferred</th>
            <th className="py-2 text-left">Confidence</th>
            <th className="py-2 text-left">Reason</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((e) => {
            const reason =
              (e.meta as any)?.reason ?? (e.meta as any)?.meta?.reason ?? null;

            return (
              <tr
                key={e.id}
                className={`border-b ${e.is_inferred ? "bg-yellow-50" : ""}`}
              >
                <td className="py-2">{fmtDateTime(e.ts)}</td>
                <td className="py-2">
                  <span
                    className={`rounded px-2 py-0.5 text-xs ${
                      e.event_type === "entry" ? "bg-green-100" : "bg-blue-100"
                    }`}
                  >
                    {e.event_type}
                  </span>
                </td>
                <td className="py-2">
                  {e.employee_id ? (
                    <code className="text-xs">{e.employee_id}</code>
                  ) : (
                    <span className="text-gray-500">unknown/visitor</span>
                  )}
                </td>
                <td className="py-2">
                  <code className="text-xs">{e.track_key}</code>
                </td>
                <td className="py-2">{e.is_inferred ? "Yes" : "No"}</td>
                <td className="py-2">
                  {e.confidence === null ? "—" : e.confidence.toFixed(3)}
                </td>
                <td className="py-2">
                  {reason ? (
                    <code className="text-xs">{String(reason)}</code>
                  ) : (
                    <span className="text-gray-500">—</span>
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
