"use client";

/**
 * components/ds/templates/ListRightPanelTemplate.tsx
 *
 * T1: List + Right Panel layout.
 *
 * Desktop: 8/12 main + 4/12 right
 * Mobile: stacked
 */

import * as React from "react";

import { cn } from "@/lib/utils";

export function ListRightPanelTemplate({
  header,
  main,
  right,
  className,
}: {
  header: React.ReactNode;
  main: React.ReactNode;
  right: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("space-y-6", className)}>
      {header}
      <div className="grid gap-6 lg:grid-cols-12">
        <div className="space-y-6 lg:col-span-8">{main}</div>
        <aside className="space-y-6 lg:col-span-4">{right}</aside>
      </div>
    </div>
  );
}

