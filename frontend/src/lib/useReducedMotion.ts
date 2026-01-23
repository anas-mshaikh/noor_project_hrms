"use client";

import { useReducedMotion as useFramerReducedMotion } from "framer-motion";

/**
 * Global reduced-motion preference hook used by the shell/navigation.
 *
 * We prefer Framer Motion's hook so all motion code can share a single,
 * well-tested source of truth.
 */
export function useReducedMotion(): boolean {
  return Boolean(useFramerReducedMotion());
}
