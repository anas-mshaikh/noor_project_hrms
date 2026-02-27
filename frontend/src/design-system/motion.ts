"use client";

/**
 * design-system/motion.ts
 *
 * Quiet, functional motion presets for the app.
 *
 * Rules:
 * - No bounce easing.
 * - Respect reduced motion: movement becomes opacity-only.
 */

import type { Transition, Variants } from "framer-motion";

export const motionDurations = {
  fast: 120,
  normal: 180,
  slow: 240,
} as const;

export const motionEasings = {
  standard: [0.2, 0, 0, 1],
  emphasize: [0.2, 0, 0.2, 1],
  entrance: [0.2, 0.9, 0.2, 1],
} as const;

function msToSeconds(ms: number): number {
  return ms / 1000;
}

export function transition(
  speed: keyof typeof motionDurations = "normal",
  ease: keyof typeof motionEasings = "standard"
): Transition {
  return {
    duration: msToSeconds(motionDurations[speed]),
    ease: motionEasings[ease],
  };
}

export function fadeInUp(reduced: boolean): Variants {
  return {
    hidden: { opacity: 0, y: reduced ? 0 : 8 },
    show: { opacity: 1, y: 0, transition: transition("normal", "entrance") },
  };
}

export function drawerInRight(reduced: boolean): Variants {
  return {
    hidden: { opacity: 0, x: reduced ? 0 : 14 },
    show: { opacity: 1, x: 0, transition: transition("normal", "entrance") },
    exit: { opacity: 0, x: reduced ? 0 : 14, transition: transition("fast") },
  };
}

export function toastIn(reduced: boolean): Variants {
  return {
    hidden: { opacity: 0, y: reduced ? 0 : 10 },
    show: { opacity: 1, y: 0, transition: transition("fast", "entrance") },
    exit: { opacity: 0, y: reduced ? 0 : 10, transition: transition("fast") },
  };
}

export function hoverLift(reduced: boolean): Variants {
  return {
    rest: { y: 0 },
    hover: { y: reduced ? 0 : -2, transition: transition("fast") },
  };
}

