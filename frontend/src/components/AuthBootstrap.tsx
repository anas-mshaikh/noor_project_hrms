"use client";

/**
 * components/AuthBootstrap.tsx
 *
 * Hydrate the frontend auth store from the backend session view (`/api/v1/auth/me`).
 *
 * Why:
 * - Tokens live in HttpOnly cookies (BFF). The browser cannot read them.
 * - The UI still needs: user identity, roles, permissions, and allowed scope ids.
 *
 * Error behavior:
 * - 401 triggers redirect to /login (handled in lib/api.ts) and clears auth state.
 * - Scope errors redirect to /scope (handled in lib/api.ts).
 */

import { useEffect } from "react";
import { usePathname } from "next/navigation";

import { apiJson } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { MeResponse } from "@/lib/types";

export function AuthBootstrap(): null {
  const pathname = usePathname();
  const setFromSession = useAuth((s) => s.setFromSession);
  const clear = useAuth((s) => s.clear);

  useEffect(() => {
    // Avoid noisy calls while the user is explicitly on the login page.
    if (pathname === "/login") return;

    let cancelled = false;
    (async () => {
      try {
        const me = await apiJson<MeResponse>("/api/v1/auth/me");
        if (!cancelled) setFromSession(me);
      } catch {
        if (!cancelled) clear();
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [pathname, setFromSession, clear]);

  return null;
}

