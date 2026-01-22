"use client";

/**
 * components/hr/GradientButton.tsx
 *
 * HR-flavored primary CTA button: subtle violet -> fuchsia gradient with a soft glow.
 *
 * We wrap the existing shadcn Button to keep ergonomics consistent.
 */

import * as React from "react";

import { Button, type ButtonProps } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function GradientButton({
  className,
  variant,
  ...props
}: ButtonProps) {
  return (
    <Button
      // Force "default" so we don't inherit an outline/ghost background that clashes
      // with the gradient. Callers can still override styles via className.
      variant={variant ?? "default"}
      className={cn(
        "relative overflow-hidden bg-gradient-to-r from-violet-500 to-fuchsia-500 text-white shadow-[0_10px_30px_-18px_rgba(168,85,247,0.9)]",
        "hover:from-violet-400 hover:to-fuchsia-400",
        "focus-visible:ring-2 focus-visible:ring-violet-300/70",
        // Tiny glow ring; keep it subtle and avoid animated loops.
        "after:pointer-events-none after:absolute after:inset-0 after:rounded-[inherit] after:ring-1 after:ring-white/10",
        className
      )}
      {...props}
    />
  );
}

