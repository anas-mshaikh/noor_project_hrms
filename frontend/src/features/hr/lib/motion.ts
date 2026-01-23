"use client";

/**
 * features/hr/lib/motion.ts
 *
 * Framer Motion variants used across HR Suite pages.
 *
 * Keep the API tiny:
 * - pageFade: page mount transition
 * - staggerContainer / staggerItem: list/card entrances
 */

import type { Variants } from "framer-motion";

export const HR_MOTION = {
  durations: {
    fast: 0.16,
    base: 0.26,
    slow: 0.42,
  },
  easing: {
    // Snappy modern UI easing.
    easeOut: [0.16, 1, 0.3, 1] as const,
    easeInOut: [0.4, 0, 0.2, 1] as const,
  },
} as const;

export function pageFade(reducedMotion: boolean): Variants {
  return {
    hidden: { opacity: 0, y: reducedMotion ? 0 : 10 },
    show: {
      opacity: 1,
      y: 0,
      transition: {
        duration: HR_MOTION.durations.slow,
        ease: HR_MOTION.easing.easeOut,
      },
    },
  };
}

export function staggerContainer(reducedMotion: boolean): Variants {
  return {
    hidden: {},
    show: {
      transition: {
        staggerChildren: reducedMotion ? 0 : 0.06,
        delayChildren: reducedMotion ? 0 : 0.04,
      },
    },
  };
}

export function staggerItem(reducedMotion: boolean): Variants {
  return {
    hidden: { opacity: 0, y: reducedMotion ? 0 : 8 },
    show: {
      opacity: 1,
      y: 0,
      transition: {
        duration: HR_MOTION.durations.base,
        ease: HR_MOTION.easing.easeOut,
      },
    },
  };
}

