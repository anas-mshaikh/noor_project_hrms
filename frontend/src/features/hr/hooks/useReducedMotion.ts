"use client";

/**
 * features/hr/hooks/useReducedMotion.ts
 *
 * Small wrapper around `prefers-reduced-motion`.
 * We use this to disable heavy transforms and long animations for accessibility.
 */

import { useEffect, useState } from "react";

export function useReducedMotion(): boolean {
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

