"use client";

import * as React from "react";

import { cn } from "@/lib/utils";

type HrHeaderProps = {
  title: string;
  subtitle?: string;
  chips?: string[];
  actions?: React.ReactNode;
  className?: string;
};

export function HrHeader({
  title,
  subtitle,
  chips,
  actions,
  className,
}: HrHeaderProps) {
  return (
    <header
      className={cn(
        "flex flex-col gap-4 md:flex-row md:items-start md:justify-between",
        className
      )}
    >
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {subtitle ? (
          <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>
        ) : null}
        {chips?.length ? (
          <div className="mt-3 flex flex-wrap gap-2">
            {chips.map((c) => (
              <span
                key={c}
                className="inline-flex items-center rounded-full bg-white/[0.04] px-3 py-1 text-xs text-muted-foreground ring-1 ring-white/10"
              >
                {c}
              </span>
            ))}
          </div>
        ) : null}
      </div>

      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </header>
  );
}

