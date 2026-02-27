"use client";

/**
 * components/ds/templates/EntityProfileTemplate.tsx
 *
 * T3: Entity profile layout scaffold.
 *
 * Provides:
 * - header
 * - tabs slot
 * - main content
 * - optional right column
 */

import * as React from "react";

import { cn } from "@/lib/utils";

export function EntityProfileTemplate({
  header,
  tabs,
  main,
  right,
  className,
}: {
  header: React.ReactNode;
  tabs?: React.ReactNode;
  main: React.ReactNode;
  right?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("space-y-6", className)}>
      {header}
      {tabs ? <div>{tabs}</div> : null}
      {right ? (
        <div className="grid gap-6 lg:grid-cols-12">
          <div className="space-y-6 lg:col-span-8">{main}</div>
          <aside className="space-y-6 lg:col-span-4">{right}</aside>
        </div>
      ) : (
        <div className="space-y-6">{main}</div>
      )}
    </div>
  );
}

