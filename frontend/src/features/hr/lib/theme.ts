"use client";

/**
 * features/hr/lib/theme.ts
 *
 * Central theme tokens for the HR Suite.
 *
 * Notes:
 * - HR pages are intentionally **dark-only** (demo-first). We don't attempt to
 *   support light mode in HR yet.
 * - Keep these tokens small and composable; components should build on top of
 *   these class strings rather than re-inventing styles per page.
 */

import { cn } from "@/lib/utils";

export const HR_THEME = {
  radius: {
    card: "rounded-3xl",
    input: "rounded-2xl",
  },
  surfaces: {
    // Primary glass surface
    card: "bg-white/[0.035]",
    // Slightly flatter surface for nested rows
    card2: "bg-white/[0.02]",
    // For headers/toolbars inside HR pages
    toolbar: "bg-white/[0.03]",
  },
  border: {
    soft: "border-border",
    hairline: "ring-1 ring-white/10",
  },
  shadow: {
    soft: "shadow-[0_18px_60px_-35px_rgba(0,0,0,0.8)]",
    glow: "shadow-[0_18px_60px_-35px_rgba(168,85,247,0.45)]",
  },
  accent: {
    gradient: "bg-gradient-to-r from-violet-500 to-fuchsia-500",
    gradientHover: "hover:from-violet-400 hover:to-fuchsia-400",
    ring: "focus-visible:ring-2 focus-visible:ring-violet-300/70",
  },
} as const;

export function glassCard(className?: string): string {
  return cn(
    "relative overflow-hidden border border-border backdrop-blur-xl",
    HR_THEME.radius.card,
    HR_THEME.surfaces.card,
    HR_THEME.shadow.soft,
    // Soft internal highlight (kept subtle so dense pages remain readable).
    "before:pointer-events-none before:absolute before:inset-0 before:bg-[radial-gradient(1200px_circle_at_15%_10%,rgba(168,85,247,0.16),transparent_55%),radial-gradient(900px_circle_at_80%_0%,rgba(236,72,153,0.12),transparent_52%)] before:opacity-70",
    // Premium hover lift (disabled for reduced motion).
    "transition-transform duration-300 motion-reduce:transition-none motion-reduce:transform-none hover:-translate-y-0.5",
    className
  );
}

export function accentGradient(className?: string): string {
  return cn(
    "text-white",
    HR_THEME.accent.gradient,
    HR_THEME.accent.gradientHover,
    HR_THEME.accent.ring,
    className
  );
}

