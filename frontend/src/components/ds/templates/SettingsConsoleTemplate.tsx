"use client";

/**
 * components/ds/templates/SettingsConsoleTemplate.tsx
 *
 * T6: Settings console scaffold (left sub-nav + right content).
 */

import * as React from "react";

import { cn } from "@/lib/utils";

export function SettingsConsoleTemplate({
  header,
  subnav,
  content,
  className,
}: {
  header?: React.ReactNode;
  subnav: React.ReactNode;
  content: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("space-y-6", className)}>
      {header ? <div>{header}</div> : null}
      <div className="grid gap-6 lg:grid-cols-12">
        <aside className="space-y-4 lg:col-span-3">{subnav}</aside>
        <section className="space-y-6 lg:col-span-9">{content}</section>
      </div>
    </div>
  );
}

