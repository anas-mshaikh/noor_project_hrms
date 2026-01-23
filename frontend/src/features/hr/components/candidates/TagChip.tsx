"use client";

import * as React from "react";

import { cn } from "@/lib/utils";

type TagChipProps = {
  children: React.ReactNode;
  className?: string;
};

export function TagChip({ children, className }: TagChipProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full bg-white/[0.04] px-2.5 py-1 text-xs text-muted-foreground ring-1 ring-white/10",
        className
      )}
    >
      {children}
    </span>
  );
}

