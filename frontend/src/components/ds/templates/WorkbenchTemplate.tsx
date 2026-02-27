"use client";

/**
 * components/ds/templates/WorkbenchTemplate.tsx
 *
 * T2: Workbench layout scaffold (list -> detail -> context).
 *
 * Desktop: 3/12 list, 6/12 detail, 3/12 context
 * Tablet/mobile: stacked (v0). Drawer behavior is a future enhancement.
 */

import * as React from "react";

import { cn } from "@/lib/utils";

export function WorkbenchTemplate({
  header,
  list,
  detail,
  context,
  className,
}: {
  header?: React.ReactNode;
  list: React.ReactNode;
  detail: React.ReactNode;
  context: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("space-y-6", className)}>
      {header ? <div>{header}</div> : null}

      <div className="grid gap-6 lg:grid-cols-12">
        <section className="space-y-4 lg:col-span-3">{list}</section>
        <section className="space-y-4 lg:col-span-6">{detail}</section>
        <aside className="space-y-4 lg:col-span-3">{context}</aside>
      </div>
    </div>
  );
}

