"use client";

/**
 * design-system/theme.ts
 *
 * Small shared class-name helpers for the design system.
 *
 * Keep this file intentionally small; it should be easy to extract later.
 */

export type SurfaceVariant = "panel" | "card" | "overlay";

export function surfaceClassName(surface: SurfaceVariant): string {
  switch (surface) {
    case "panel":
      return "bg-surface-1";
    case "overlay":
      return "bg-surface-3";
    case "card":
    default:
      return "bg-surface-2";
  }
}

export function surfaceShadowClassName(surface: SurfaceVariant): string {
  if (surface === "overlay") return "shadow-[var(--ds-elevation-glow)]";
  if (surface === "panel") return "shadow-[var(--ds-elevation-panel)]";
  return "shadow-[var(--ds-elevation-subtle)]";
}

