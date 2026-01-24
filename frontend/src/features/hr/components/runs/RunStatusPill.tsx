"use client";

import * as React from "react";

import { TagChip } from "@/features/hr/components/candidates/TagChip";
import { cn } from "@/lib/utils";

type RunStatusPillProps = {
  status: string | undefined | null;
  className?: string;
};

function statusClass(status: string): string {
  switch (status) {
    case "DONE":
      return "bg-emerald-500/10 text-emerald-100 ring-emerald-500/20";
    case "RUNNING":
      return "bg-violet-500/10 text-violet-100 ring-violet-500/20";
    case "QUEUED":
      return "bg-white/[0.04] text-muted-foreground ring-white/10";
    case "FAILED":
      return "bg-rose-500/10 text-rose-100 ring-rose-500/25";
    case "CANCELLED":
      return "bg-amber-500/10 text-amber-100 ring-amber-500/25";
    default:
      return "bg-white/[0.04] text-muted-foreground ring-white/10";
  }
}

export function RunStatusPill({ status, className }: RunStatusPillProps) {
  const label = (status ?? "—").toString();
  return (
    <TagChip className={cn(statusClass(label), className)}>{label}</TagChip>
  );
}

