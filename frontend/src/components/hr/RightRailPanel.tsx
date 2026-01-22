"use client";

/**
 * components/hr/RightRailPanel.tsx
 *
 * A simple "right rail" list panel used on the HR Overview page.
 * Built with the HR-local GlassCard primitive so it doesn't affect the rest of the app.
 */

import * as React from "react";
import type { LucideIcon } from "lucide-react";

import { GlassCard } from "@/components/hr/GlassCard";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

export type RightRailItem = {
  id: string;
  title: string;
  subtitle?: string;
  meta?: string;
  icon?: LucideIcon;
};

export type RightRailPanelProps = {
  title: string;
  actionLabel?: string;
  onAction?: () => void;
  items: RightRailItem[];
  loading?: boolean;
  className?: string;
};

export function RightRailPanel({
  title,
  actionLabel,
  onAction,
  items,
  loading,
  className,
}: RightRailPanelProps) {
  return (
    <GlassCard className={cn("p-5", className)}>
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm font-semibold tracking-tight">{title}</div>
        {actionLabel ? (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={onAction}
            className="h-8 rounded-xl px-2 text-white/70 hover:bg-white/10 hover:text-white"
          >
            {actionLabel}
          </Button>
        ) : null}
      </div>

      <div className="mt-4 space-y-3">
        {loading ? (
          <>
            {Array.from({ length: 4 }).map((_, i) => (
              <div
                key={i}
                className="flex items-center justify-between gap-3 rounded-2xl bg-white/[0.02] p-3 ring-1 ring-white/5"
              >
                <div className="flex items-center gap-3">
                  <Skeleton className="h-9 w-9 rounded-xl bg-white/10" />
                  <div className="space-y-2">
                    <Skeleton className="h-3 w-36 bg-white/10" />
                    <Skeleton className="h-3 w-24 bg-white/10" />
                  </div>
                </div>
                <Skeleton className="h-3 w-16 bg-white/10" />
              </div>
            ))}
          </>
        ) : items.length === 0 ? (
          <div className="rounded-2xl bg-white/[0.02] p-4 text-sm text-white/60 ring-1 ring-white/5">
            Nothing here yet.
          </div>
        ) : (
          items.map((it) => {
            const Icon = it.icon;
            return (
              <div
                key={it.id}
                className="flex items-center justify-between gap-3 rounded-2xl bg-white/[0.02] p-3 ring-1 ring-white/5"
              >
                <div className="flex min-w-0 items-center gap-3">
                  <div className="relative h-9 w-9 shrink-0 rounded-xl bg-white/5 ring-1 ring-white/10">
                    <div className="pointer-events-none absolute inset-0 rounded-xl bg-[radial-gradient(16px_circle_at_30%_25%,rgba(168,85,247,0.32),transparent_60%)]" />
                    {Icon ? (
                      <Icon className="absolute left-1/2 top-1/2 h-4 w-4 -translate-x-1/2 -translate-y-1/2 text-white/80" />
                    ) : (
                      <div className="absolute left-1/2 top-1/2 h-2 w-2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-white/70" />
                    )}
                  </div>

                  <div className="min-w-0">
                    <div className="truncate text-sm font-medium">
                      {it.title}
                    </div>
                    {it.subtitle ? (
                      <div className="truncate text-xs text-white/60">
                        {it.subtitle}
                      </div>
                    ) : null}
                  </div>
                </div>

                {it.meta ? (
                  <div className="shrink-0 text-xs text-white/60">{it.meta}</div>
                ) : null}
              </div>
            );
          })
        )}
      </div>
    </GlassCard>
  );
}

