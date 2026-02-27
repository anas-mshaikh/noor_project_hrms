"use client";

/**
 * components/ds/EmptyState.tsx
 *
 * Actionable empty state used in list panes and card bodies.
 */

import * as React from "react";
import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

export function EmptyState({
  icon,
  title,
  description,
  primaryAction,
  secondaryAction,
  align = "start",
  className,
}: {
  icon?: LucideIcon | React.ReactNode;
  title: string;
  description?: string;
  primaryAction?: React.ReactNode;
  secondaryAction?: React.ReactNode;
  align?: "start" | "center";
  className?: string;
}) {
  let iconNode: React.ReactNode = null;
  if (typeof icon === "function") {
    const Icon = icon as LucideIcon;
    iconNode = <Icon className="h-5 w-5 text-text-2" />;
  } else {
    iconNode = icon ?? null;
  }

  return (
    <div
      className={cn(
        "flex flex-col gap-2",
        align === "center" ? "items-center text-center" : "items-start",
        className
      )}
    >
      {iconNode ? (
        <div className="inline-flex h-10 w-10 items-center justify-center rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1">
          {iconNode}
        </div>
      ) : null}

      <div className="space-y-1">
        <div className="text-sm font-medium text-text-1">{title}</div>
        {description ? (
          <div className="text-sm text-text-2">{description}</div>
        ) : null}
      </div>

      {primaryAction || secondaryAction ? (
        <div className="mt-2 flex flex-wrap items-center gap-2">
          {primaryAction}
          {secondaryAction}
        </div>
      ) : null}
    </div>
  );
}
