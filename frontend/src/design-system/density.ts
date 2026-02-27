"use client";

/**
 * design-system/density.ts
 *
 * Density mode helpers used by DS components (tables, cards).
 *
 * Density is implemented via CSS variables (see `design-system/tokens.css`) so
 * it can be applied via a class without duplicating sizes across components.
 */

export type DensityMode = "comfortable" | "compact";

export function densityClassName(density: DensityMode): string {
  return density === "compact" ? "ds-density-compact" : "ds-density-comfortable";
}

