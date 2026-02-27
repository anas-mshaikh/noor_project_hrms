"use client";

/**
 * components/ds/PageHeader.tsx
 *
 * Standard page header:
 * - title + subtitle
 * - optional breadcrumb
 * - optional actions (aligned to inline-end)
 * - optional meta row (chips)
 */

import * as React from "react";

import { cn } from "@/lib/utils";

export function PageHeader({
  title,
  subtitle,
  breadcrumb,
  actions,
  meta,
  className,
}: {
  title: string;
  subtitle?: string;
  breadcrumb?: React.ReactNode;
  actions?: React.ReactNode;
  meta?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("space-y-3", className)}>
      {breadcrumb ? <div className="text-sm text-text-2">{breadcrumb}</div> : null}

      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div className="min-w-0">
          <h1 className="text-2xl font-semibold tracking-tight text-text-1">
            {title}
          </h1>
          {subtitle ? (
            <p className="mt-1 text-sm text-text-2">{subtitle}</p>
          ) : null}
        </div>

        {actions ? <div className="shrink-0">{actions}</div> : null}
      </div>

      {meta ? <div className="flex flex-wrap gap-2">{meta}</div> : null}
    </div>
  );
}

