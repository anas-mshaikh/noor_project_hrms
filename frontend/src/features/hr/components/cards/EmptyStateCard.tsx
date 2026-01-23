"use client";

import * as React from "react";
import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";
import { GlassCard } from "@/features/hr/components/cards/GlassCard";

type EmptyStateCardProps = {
  title: string;
  description?: string;
  icon?: LucideIcon;
  actions?: React.ReactNode;
  className?: string;
};

export function EmptyStateCard({
  title,
  description,
  icon: Icon,
  actions,
  className,
}: EmptyStateCardProps) {
  return (
    <GlassCard className={cn("p-6", className)}>
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="text-sm font-semibold tracking-tight">{title}</div>
          {description ? (
            <p className="mt-1 text-sm text-muted-foreground">{description}</p>
          ) : null}
        </div>
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-white/5 ring-1 ring-white/10">
          {Icon ? <Icon className="h-5 w-5 text-foreground/80" /> : null}
        </div>
      </div>
      {actions ? <div className="mt-4 flex flex-wrap gap-2">{actions}</div> : null}
    </GlassCard>
  );
}

