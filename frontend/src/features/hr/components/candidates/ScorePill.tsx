"use client";

import * as React from "react";

import { cn } from "@/lib/utils";

type ScorePillProps = {
  score: number;
  className?: string;
};

function scoreTone(score: number): string {
  if (score >= 85) return "bg-emerald-500/15 text-emerald-200 ring-emerald-400/20";
  if (score >= 70) return "bg-violet-500/15 text-violet-200 ring-violet-400/25";
  return "bg-white/5 text-muted-foreground ring-white/10";
}

export function ScorePill({ score, className }: ScorePillProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium ring-1 tabular-nums",
        scoreTone(score),
        className
      )}
      aria-label={`Fit score ${score} out of 100`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current/70" />
      {score}
    </span>
  );
}

