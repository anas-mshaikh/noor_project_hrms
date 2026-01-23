"use client";

import * as React from "react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/features/hr/components/cards/GlassCard";

type PanelCardProps = {
  title: string;
  description?: string;
  actionLabel?: string;
  onAction?: () => void;
  children: React.ReactNode;
  className?: string;
};

export function PanelCard({
  title,
  description,
  actionLabel,
  onAction,
  children,
  className,
}: PanelCardProps) {
  return (
    <GlassCard className={cn("p-5", className)}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-sm font-semibold tracking-tight">{title}</div>
          {description ? (
            <div className="mt-1 text-xs text-muted-foreground">{description}</div>
          ) : null}
        </div>
        {actionLabel ? (
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={onAction}
            className="h-8 rounded-xl px-2 text-muted-foreground hover:bg-accent hover:text-foreground"
          >
            {actionLabel}
          </Button>
        ) : null}
      </div>

      <div className="mt-4">{children}</div>
    </GlassCard>
  );
}

