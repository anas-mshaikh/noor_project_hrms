"use client";

/**
 * components/ds/DataView.tsx
 *
 * Lightweight page scaffold for list/detail screens.
 */

import * as React from "react";

import { cn } from "@/lib/utils";

export function DataView({
  header,
  children,
  className,
}: {
  header: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("space-y-6", className)}>
      {header}
      {children}
    </div>
  );
}

