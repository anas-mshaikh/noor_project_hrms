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

import { ApiError, apiJson } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useSelection } from "@/lib/selection";
import type { MeResponse } from "@/lib/types";

export function AuthBootstrap(): null {
  const pathname = usePathname();
  const setFromSession = useAuth((s) => s.setFromSession);
  const clear = useAuth((s) => s.clear);

  const selectedTenantId = useSelection((s) => s.tenantId);
  const selectedCompanyId = useSelection((s) => s.companyId);
  const selectedBranchId = useSelection((s) => s.branchId);
  const setTenantId = useSelection((s) => s.setTenantId);
  const setCompanyId = useSelection((s) => s.setCompanyId);
  const setBranchId = useSelection((s) => s.setBranchId);

  useEffect(() => {
    // Avoid noisy calls while the user is explicitly on the login page.
    //
    // Also skip /setup: it must be reachable on a fresh DB so the user can run
    // bootstrap without being redirected to /login by the global 401 handler.
    if (pathname === "/login" || pathname === "/setup") return;

    let cancelled = false;
    (async () => {
      try {
        const me = await apiJson<MeResponse>("/api/v1/auth/me");
        if (cancelled) return;

        setFromSession(me);

        // Keep local selection aligned with the server-validated scope.
        // This prevents stale company/branch ids from locking users into
        // `iam.scope.forbidden` loops.
        const tenantId = String(me.scope.tenant_id);
        const companyId = me.scope.company_id ? String(me.scope.company_id) : undefined;
        const branchId = me.scope.branch_id ? String(me.scope.branch_id) : undefined;

        if (selectedTenantId !== tenantId) {
          // Changing tenant clears dependent selections.
          setTenantId(tenantId);
        }
        if (selectedCompanyId !== companyId) {
          setCompanyId(companyId);
        }
        if (selectedBranchId !== branchId) {
          setBranchId(branchId);
        }
      } catch (err) {
        /**
         * `/auth/me` can fail for reasons other than an expired session:
         * - transient network errors
         * - fail-closed scope errors (selection drift)
         *
         * The API layer already redirects to /login on 401 and /scope on scope errors.
         * Avoid wiping the auth store on those recoverable cases; keep last-known
         * permissions so nav doesn't flicker or disappear.
         */
        if (!cancelled) {
          if (err instanceof ApiError && err.status !== 401) return;
          clear();
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [
    pathname,
    setFromSession,
    clear,
    selectedTenantId,
    selectedCompanyId,
    selectedBranchId,
    setTenantId,
    setCompanyId,
    setBranchId,
  ]);

  return null;
}
