"use client";

/**
 * components/hr/GlassCard.tsx
 *
 * A minimal "purple glass" card primitive for HR pages.
 *
 * This intentionally does NOT change the global shadcn Card component.
 * We keep the styling local to HR so existing pages remain unchanged.
 */

import * as React from "react";
import { Slot } from "@radix-ui/react-slot";

import { cn } from "@/lib/utils";

type GlassCardProps = React.HTMLAttributes<HTMLDivElement> & {
  asChild?: boolean;
};

export function GlassCard({ asChild, className, ...props }: GlassCardProps) {
  const Comp = asChild ? Slot : "div";
  return (
    <Comp
      className={cn(
        "group relative overflow-hidden rounded-3xl border border-white/10 bg-white/[0.035] text-white shadow-[0_18px_60px_-35px_rgba(0,0,0,0.8)] backdrop-blur-xl",
        // Subtle hover lift (disabled for reduced motion).
        "transition-transform duration-300 motion-reduce:transition-none motion-reduce:transform-none hover:-translate-y-0.5",
        // Soft inner highlight.
        "before:pointer-events-none before:absolute before:inset-0 before:bg-[radial-gradient(1200px_circle_at_15%_10%,rgba(168,85,247,0.18),transparent_55%),radial-gradient(900px_circle_at_80%_0%,rgba(236,72,153,0.14),transparent_52%)] before:opacity-70",
        className
      )}
      {...props}
    />
  );
}

