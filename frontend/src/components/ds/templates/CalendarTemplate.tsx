"use client";

/**
 * components/ds/templates/CalendarTemplate.tsx
 *
 * T4: Calendar scaffold (layout only, no calendar logic).
 */

import * as React from "react";

import { cn } from "@/lib/utils";

export function CalendarTemplate({
  header,
  calendar,
  right,
  className,
}: {
  header: React.ReactNode;
  calendar: React.ReactNode;
  right?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("space-y-6", className)}>
      {header}
      {right ? (
        <div className="grid gap-6 lg:grid-cols-12">
          <div className="space-y-6 lg:col-span-8">{calendar}</div>
          <aside className="space-y-6 lg:col-span-4">{right}</aside>
        </div>
      ) : (
        <div className="space-y-6">{calendar}</div>
      )}
    </div>
  );
}

