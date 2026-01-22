"use client";

/**
 * lib/motion.ts
 *
 * A tiny motion helper layer for the HR pages.
 *
 * Goals:
 * - Keep motion consistent across HR pages (variants + timing).
 * - Respect `prefers-reduced-motion` (opacity-only, no big transforms).
 * - Keep the rest of the app unchanged (this is HR-scoped).
 */

import { useEffect, useState } from "react";
import type { Variants } from "framer-motion";

export function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const onChange = () => setReduced(Boolean(mq.matches));
    onChange();

    // Safari < 14 fallback: addListener/removeListener.
    if (typeof mq.addEventListener === "function") {
      mq.addEventListener("change", onChange);
      return () => mq.removeEventListener("change", onChange);
    }

    const legacyMq = mq as unknown as {
      addListener?: (cb: () => void) => void;
      removeListener?: (cb: () => void) => void;
    };
    legacyMq.addListener?.(onChange);
    return () => legacyMq.removeListener?.(onChange);
  }, []);

  return reduced;
}

export const MOTION = {
  durations: {
    fast: 0.16,
    base: 0.26,
    slow: 0.42,
  },
  easing: {
    // Matches a modern "snappy" UI feel.
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
        duration: MOTION.durations.slow,
        ease: MOTION.easing.easeOut,
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
        duration: MOTION.durations.base,
        ease: MOTION.easing.easeOut,
      },
    },
  };
}
