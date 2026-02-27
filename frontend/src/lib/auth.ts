"use client";

/**
 * lib/auth.ts
 *
 * Persist a minimal auth *session view* in localStorage.
 *
 * This is intentionally minimal:
 * - Tokens are stored in HttpOnly cookies via the BFF proxy (see `app/api/v1/*`).
 * - Frontend stores only non-secret identity/scope/permissions to render UI safely.
 */

import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { MeResponse } from "@/lib/types";

type AuthState = {
  user?: MeResponse["user"];
  roles: string[];
  permissions: string[];
  scope?: MeResponse["scope"];

  setFromSession: (s: MeResponse) => void;
  clear: () => void;
};

export const useAuth = create<AuthState>()(
  persist(
    (set) => ({
      user: undefined,
      roles: [],
      permissions: [],
      scope: undefined,

      setFromSession: (s) =>
        set({
          user: s.user,
          roles: s.roles ?? [],
          permissions: s.permissions ?? [],
          scope: s.scope,
        }),

      clear: () =>
        set({
          user: undefined,
          roles: [],
          permissions: [],
          scope: undefined,
        }),
    }),
    { name: "attendance-admin-auth" }
  )
);
