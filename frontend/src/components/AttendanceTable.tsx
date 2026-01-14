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
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

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
    return <div className="text-sm text-muted-foreground">No attendance rows.</div>;
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Code</TableHead>
          <TableHead>Name</TableHead>
          <TableHead>Punch in</TableHead>
          <TableHead>Punch out</TableHead>
          <TableHead>Total (min)</TableHead>
          <TableHead>Anomalies</TableHead>
        </TableRow>
      </TableHeader>

      <TableBody>
        {rows.map((r) => {
          const anomalies = summarizeAnomalies(r.anomalies_json ?? {});
          const absent = Boolean(
            (r.anomalies_json as { absent?: boolean } | null)?.absent
          );

          return (
            <TableRow key={r.employee_id} className={absent ? "bg-muted/30" : ""}>
              <TableCell className="font-mono text-xs">
                {r.employee_code}
              </TableCell>
              <TableCell className="font-medium">{r.employee_name}</TableCell>
              <TableCell>{fmtDateTime(r.punch_in)}</TableCell>
              <TableCell>{fmtDateTime(r.punch_out)}</TableCell>
              <TableCell className="tabular-nums">
                {r.total_minutes === null ? "—" : r.total_minutes}
              </TableCell>
              <TableCell>
                {anomalies.length === 0 ? (
                  <span className="text-muted-foreground">—</span>
                ) : (
                  <div className="flex flex-wrap gap-1">
                    {anomalies.map((k) => (
                      <Badge key={k} variant="secondary">
                        {k}
                      </Badge>
                    ))}
                  </div>
                )}
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
