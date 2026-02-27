"use client";

/**
 * components/ds/AuditTimeline.tsx
 *
 * Simple vertical timeline intended for "trust cues" (audit-like events).
 *
 * This is UI-only in v0; wiring to backend audit logs is a future milestone.
 */

import * as React from "react";

import { cn } from "@/lib/utils";

type Tone = "neutral" | "success" | "warning" | "danger" | "info";

function dotClassName(tone: Tone): string {
  switch (tone) {
    case "success":
      return "bg-success";
    case "warning":
      return "bg-warning";
    case "danger":
      return "bg-danger";
    case "info":
      return "bg-info";
    case "neutral":
    default:
      return "bg-text-3";
  }
}

export type AuditTimelineItem = {
  title: string;
  time?: string;
  description?: string;
  tone?: Tone;
};

export function AuditTimeline({
  items,
  className,
}: {
  items: AuditTimelineItem[];
  className?: string;
}) {
  return (
    <div className={cn("space-y-3", className)}>
      {items.map((it, idx) => {
        const tone: Tone = it.tone ?? "neutral";
        return (
          <div key={idx} className="flex gap-3">
            <div className="flex flex-col items-center">
              <div
                className={cn(
                  "mt-1 h-2.5 w-2.5 rounded-full",
                  dotClassName(tone)
                )}
              />
              {idx < items.length - 1 ? (
                <div className="mt-2 h-full w-px bg-border-subtle" />
              ) : null}
            </div>

            <div className="min-w-0 pb-1">
              <div className="flex flex-wrap items-baseline gap-2">
                <div className="text-sm font-medium text-text-1">{it.title}</div>
                {it.time ? (
                  <div className="text-xs text-text-3">{it.time}</div>
                ) : null}
              </div>
              {it.description ? (
                <div className="mt-1 text-sm text-text-2">{it.description}</div>
              ) : null}
            </div>
          </div>
        );
      })}
    </div>
  );
}

