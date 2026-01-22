"use client";

/**
 * components/hr/StatCard.tsx
 *
 * Compact KPI card used on the HR Overview page.
 */

import * as React from "react";
import type { LucideIcon } from "lucide-react";

import { GlassCard } from "@/components/hr/GlassCard";
import { cn } from "@/lib/utils";

export type StatCardProps = {
  label: string;
  value?: string | number;
  delta?: string;
  icon?: LucideIcon;
  loading?: boolean;
  className?: string;
};

export function StatCard({
  label,
  value,
  delta,
  icon: Icon,
  loading,
  className,
}: StatCardProps) {
  return (
    <GlassCard className={cn("p-5", className)}>
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="text-xs font-medium text-white/70">{label}</div>
          <div className="mt-2">
            {loading ? (
              <div className="h-8 w-24 animate-pulse rounded-lg bg-white/10" />
            ) : (
              <div className="text-3xl font-semibold tracking-tight">
                {value ?? "—"}
              </div>
            )}
          </div>
          {delta ? (
            <div className="mt-2 text-xs text-emerald-200/90">{delta}</div>
          ) : (
            <div className="mt-2 text-xs text-white/50"> </div>
          )}
        </div>

        <div className="flex shrink-0 items-center gap-3">
          {/* Decorative "ring" + icon */}
          <div className="relative h-10 w-10 rounded-2xl bg-white/5 ring-1 ring-white/10">
            <div className="pointer-events-none absolute inset-0 rounded-2xl bg-[radial-gradient(18px_circle_at_30%_25%,rgba(168,85,247,0.35),transparent_60%)]" />
            {Icon ? (
              <Icon className="absolute left-1/2 top-1/2 h-5 w-5 -translate-x-1/2 -translate-y-1/2 text-white/80" />
            ) : null}
          </div>
        </div>
      </div>
    </GlassCard>
  );
}

