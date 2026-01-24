"use client";

import * as React from "react";

import { cn } from "@/lib/utils";
import { useReducedMotion } from "@/features/hr/hooks/useReducedMotion";

type RunProgressBarProps = {
  progressDone: number;
  progressTotal: number;
  className?: string;
};

export function RunProgressBar({
  progressDone,
  progressTotal,
  className,
}: RunProgressBarProps) {
  const reduced = useReducedMotion();
  const total = Math.max(0, Number(progressTotal) || 0);
  const done = Math.max(0, Number(progressDone) || 0);
  const clampedDone = total > 0 ? Math.min(done, total) : done;
  const pct = total > 0 ? Math.round((clampedDone / total) * 100) : null;

  return (
    <div className={cn("space-y-2", className)}>
      <div className="flex items-center justify-between text-xs text-muted-foreground tabular-nums">
        <span>{pct != null ? `${pct}%` : "Starting…"}</span>
        <span>{total > 0 ? `${clampedDone}/${total}` : "—"}</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-white/5 ring-1 ring-white/10">
        {total > 0 ? (
          <div
            className="h-full bg-violet-400/40"
            style={{ width: `${Math.max(0, Math.min(100, pct ?? 0))}%` }}
          />
        ) : (
          <div
            className={cn(
              "h-full w-1/3 bg-violet-400/30",
              reduced ? "" : "animate-pulse"
            )}
          />
        )}
      </div>
    </div>
  );
}

