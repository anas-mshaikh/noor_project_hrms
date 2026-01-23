"use client";

/**
 * features/hr/hooks/useMockLoading.ts
 *
 * Demo helper to simulate network loading while the backend wiring is not ready.
 */

import { useEffect, useState } from "react";

export function useMockLoading(delayMs: number = 600): {
  loading: boolean;
  done: boolean;
} {
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const t = window.setTimeout(() => setLoading(false), Math.max(0, delayMs));
    return () => window.clearTimeout(t);
  }, [delayMs]);

  return { loading, done: !loading };
}

