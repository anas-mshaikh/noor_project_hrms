"use client";

/**
 * lib/auth.ts
 *
 * Persist auth session (JWT access/refresh tokens + scope) in localStorage.
 *
 * This is intentionally minimal:
 * - Backend is the source of truth for permissions.
 * - We store enough to attach Authorization headers and render basic UI.
 */

import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { TokenResponse } from "@/lib/types";

type AuthState = {
  accessToken?: string;
  refreshToken?: string;
  user?: TokenResponse["user"];
  roles: string[];
  scope?: TokenResponse["scope"];

  setFromTokenResponse: (t: TokenResponse) => void;
  clear: () => void;
};

export const useAuth = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: undefined,
      refreshToken: undefined,
      user: undefined,
      roles: [],
      scope: undefined,

      setFromTokenResponse: (t) =>
        set({
          accessToken: t.access_token,
          refreshToken: t.refresh_token,
          user: t.user,
          roles: t.roles ?? [],
          scope: t.scope,
        }),

      clear: () =>
        set({
          accessToken: undefined,
          refreshToken: undefined,
          user: undefined,
          roles: [],
          scope: undefined,
        }),
    }),
    { name: "attendance-admin-auth" }
  )
);

