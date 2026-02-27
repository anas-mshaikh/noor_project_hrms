"use client";

/**
 * components/ds/DSCard.tsx
 *
 * Design-system card surface wrapper.
 *
 * This intentionally does not depend on the existing `ui/Card` primitive so DS
 * surfaces can be tuned without affecting legacy pages.
 */

import * as React from "react";

import { densityClassName, type DensityMode } from "@/design-system/density";
import { surfaceClassName, surfaceShadowClassName, type SurfaceVariant } from "@/design-system/theme";
import { cn } from "@/lib/utils";

export type DSCardProps = React.HTMLAttributes<HTMLDivElement> & {
  surface?: SurfaceVariant;
  density?: DensityMode;
};

export function DSCard({
  surface = "card",
  density = "comfortable",
  className,
  children,
  ...props
}: DSCardProps) {
  return (
    <div
      className={cn(
        "relative overflow-hidden border backdrop-blur-xl",
        "rounded-[var(--ds-radius-20)]",
        "border-border-subtle",
        surfaceClassName(surface),
        surfaceShadowClassName(surface),
        densityClassName(density),
        // Soft inner highlight (kept subtle so it doesn't distract on dense pages).
        "before:pointer-events-none before:absolute before:inset-0 before:bg-[radial-gradient(900px_circle_at_10%_0%,rgba(168,85,247,0.10),transparent_55%),radial-gradient(700px_circle_at_90%_10%,rgba(236,72,153,0.07),transparent_55%)] before:opacity-80",
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}

