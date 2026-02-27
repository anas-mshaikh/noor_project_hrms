"use client";

/**
 * components/ds/RightPanelStack.tsx
 *
 * Right column container for stacked cards/widgets.
 */

import * as React from "react";

import { cn } from "@/lib/utils";

export function RightPanelStack({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <div className={cn("space-y-4", className)}>{children}</div>;
}

