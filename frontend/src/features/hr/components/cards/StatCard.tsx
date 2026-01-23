"use client";

import * as React from "react";
import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";
import { GlassCard } from "@/features/hr/components/cards/GlassCard";

export type HrStatCardProps = {
  label: string;
  value?: string | number;
  subLabel?: string;
  trend?: string;
  icon?: LucideIcon;
  loading?: boolean;
  className?: string;
};

export function StatCard({
  label,
  value,
  subLabel,
  trend,
  icon: Icon,
  loading,
  className,
}: HrStatCardProps) {
  return (
    <GlassCard className={cn("p-5", className)}>
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="text-xs font-medium text-muted-foreground">{label}</div>
          <div className="mt-2">
            {loading ? (
              <Skeleton className="h-8 w-28 rounded-lg bg-white/10" />
            ) : (
              <div className="text-3xl font-semibold tracking-tight tabular-nums">
                {value ?? "—"}
              </div>
            )}
          </div>
          {subLabel ? (
            <div className="mt-2 text-xs text-muted-foreground">{subLabel}</div>
          ) : null}
          {trend ? (
            <div className="mt-2 text-xs text-emerald-300">{trend}</div>
          ) : (
            <div className="mt-2 text-xs text-muted-foreground/60"> </div>
          )}
        </div>

        <div className="flex shrink-0 items-center gap-3">
          <div className="relative h-10 w-10 rounded-2xl bg-white/5 ring-1 ring-white/10">
            <div className="pointer-events-none absolute inset-0 rounded-2xl bg-[radial-gradient(18px_circle_at_30%_25%,rgba(168,85,247,0.35),transparent_60%)]" />
            {Icon ? (
              <Icon className="absolute left-1/2 top-1/2 h-5 w-5 -translate-x-1/2 -translate-y-1/2 text-foreground/80" />
            ) : null}
          </div>
        </div>
      </div>
    </GlassCard>
  );
}

