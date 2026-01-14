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

import { useState } from "react";

import type { EventOut } from "@/lib/types";
import { apiUrl } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

function fmtDateTime(dt: string): string {
  return new Date(dt).toLocaleString();
}

function getReason(meta: Record<string, unknown>): string | null {
  const direct = meta["reason"];
  if (typeof direct === "string" && direct.length > 0) return direct;

  const nested = meta["meta"];
  if (nested && typeof nested === "object") {
    const nestedReason = (nested as Record<string, unknown>)["reason"];
    if (typeof nestedReason === "string" && nestedReason.length > 0) {
      return nestedReason;
    }
  }

  return null;
}

export function EventsTable({ rows }: { rows: EventOut[] }) {
  const [preview, setPreview] = useState<EventOut | null>(null);

  if (rows.length === 0) {
    return <div className="text-sm text-muted-foreground">No events.</div>;
  }

  return (
    <div>
      <Dialog
        open={Boolean(preview)}
        onOpenChange={(open) => {
          if (!open) setPreview(null);
        }}
      >
        {preview && (
          <DialogContent className="max-w-4xl">
            <DialogHeader>
              <DialogTitle>
                Snapshot • {preview.event_type} • {fmtDateTime(preview.ts)}
              </DialogTitle>
            </DialogHeader>

            <div className="mt-3">
              <img
                src={apiUrl(`/api/v1/events/${preview.id}/snapshot`)}
                alt={`${preview.event_type} snapshot`}
                className="max-h-[72vh] w-full rounded object-contain"
              />
            </div>

            <DialogFooter className="mt-4">
              <Button asChild variant="outline">
                <a
                  href={apiUrl(`/api/v1/events/${preview.id}/snapshot`)}
                  target="_blank"
                  rel="noreferrer"
                >
                  Open in new tab
                </a>
              </Button>
              <Button type="button" onClick={() => setPreview(null)}>
                Close
              </Button>
            </DialogFooter>
          </DialogContent>
        )}
      </Dialog>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Time</TableHead>
            <TableHead>Type</TableHead>
            <TableHead>Snapshot</TableHead>
            <TableHead>Employee</TableHead>
            <TableHead>Track</TableHead>
            <TableHead>Inferred</TableHead>
            <TableHead>Confidence</TableHead>
            <TableHead>Reason</TableHead>
          </TableRow>
        </TableHeader>

        <TableBody>
          {rows.map((e) => {
            const meta = (e.meta as Record<string, unknown> | null) ?? {};
            const reason = getReason(meta);

            return (
              <TableRow
                key={e.id}
                className={e.is_inferred ? "bg-muted/30" : ""}
              >
                <TableCell className="whitespace-nowrap">
                  {fmtDateTime(e.ts)}
                </TableCell>

                <TableCell>
                  <Badge
                    variant="secondary"
                    className={
                      e.event_type === "entry"
                        ? "bg-emerald-500/15 text-emerald-700"
                        : "bg-blue-500/15 text-blue-700"
                    }
                  >
                    {e.event_type}
                  </Badge>
                </TableCell>

                <TableCell>
                  {e.snapshot_path ? (
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="h-auto justify-start gap-2 px-0"
                      title="Preview snapshot"
                      onClick={() => setPreview(e)}
                    >
                      <img
                        src={apiUrl(`/api/v1/events/${e.id}/snapshot`)}
                        alt={`${e.event_type} snapshot`}
                        className="h-10 w-10 rounded-md border object-cover"
                        loading="lazy"
                      />
                      <span className="text-xs underline">view</span>
                    </Button>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </TableCell>

                <TableCell>
                  {e.employee_id ? (
                    <code className="text-xs">{e.employee_id}</code>
                  ) : (
                    <span className="text-muted-foreground">unknown/visitor</span>
                  )}
                </TableCell>

                <TableCell>
                  <code className="text-xs">{e.track_key}</code>
                </TableCell>

                <TableCell>
                  {e.is_inferred ? (
                    <Badge variant="outline">Yes</Badge>
                  ) : (
                    <span className="text-muted-foreground">No</span>
                  )}
                </TableCell>

                <TableCell className="tabular-nums">
                  {e.confidence === null ? "—" : e.confidence.toFixed(3)}
                </TableCell>

                <TableCell>
                  {reason ? (
                    <code className="text-xs">{String(reason)}</code>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
