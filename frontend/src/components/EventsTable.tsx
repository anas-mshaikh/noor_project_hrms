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
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

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
    return <div className="text-sm text-gray-600">No events.</div>;
  }

  return (
    <div className="overflow-auto">
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

      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b">
            <th className="py-2 text-left">Time</th>
            <th className="py-2 text-left">Type</th>
            <th className="py-2 text-left">Snapshot</th>
            <th className="py-2 text-left">Employee</th>
            <th className="py-2 text-left">Track</th>
            <th className="py-2 text-left">Inferred</th>
            <th className="py-2 text-left">Confidence</th>
            <th className="py-2 text-left">Reason</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((e) => {
            const meta = (e.meta as Record<string, unknown> | null) ?? {};
            const reason = getReason(meta);

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
                  {e.snapshot_path ? (
                    <button
                      type="button"
                      className="inline-flex items-center gap-2"
                      title="Preview snapshot"
                      onClick={() => setPreview(e)}
                    >
                      <img
                        src={apiUrl(`/api/v1/events/${e.id}/snapshot`)}
                        alt={`${e.event_type} snapshot`}
                        className="h-10 w-10 rounded border object-cover"
                        loading="lazy"
                      />
                      <span className="text-xs text-blue-600 underline">
                        view
                      </span>
                    </button>
                  ) : (
                    <span className="text-gray-500">—</span>
                  )}
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
