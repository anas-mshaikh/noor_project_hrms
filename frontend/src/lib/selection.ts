"use client";

/**
 * lib/selection.ts
 *
 * Persist tenant/company/branch/camera selection in localStorage.
 *
 * IMPORTANT: "use client" is required because Zustand persist uses localStorage,
 * which does not exist on the server.
 */

import { create } from "zustand";
import { persist } from "zustand/middleware";

const SCOPE_TENANT_COOKIE = "noor_scope_tenant_id";
const SCOPE_COMPANY_COOKIE = "noor_scope_company_id";
const SCOPE_BRANCH_COOKIE = "noor_scope_branch_id";

function cookieSecure(): boolean {
  if (typeof window === "undefined") return false;
  return window.location.protocol === "https:" || process.env.NODE_ENV === "production";
}

function setCookie(name: string, value: string): void {
  if (typeof document === "undefined") return;
  const secure = cookieSecure() ? "; Secure" : "";
  document.cookie = `${name}=${encodeURIComponent(value)}; Path=/; SameSite=Lax${secure}`;
}

function deleteCookie(name: string): void {
  if (typeof document === "undefined") return;
  const secure = cookieSecure() ? "; Secure" : "";
  document.cookie = `${name}=; Path=/; Max-Age=0; SameSite=Lax${secure}`;
}

function syncScopeCookies(next: { tenantId?: string; companyId?: string; branchId?: string }): void {
  if (next.tenantId) setCookie(SCOPE_TENANT_COOKIE, next.tenantId);
  else deleteCookie(SCOPE_TENANT_COOKIE);

  if (next.companyId) setCookie(SCOPE_COMPANY_COOKIE, next.companyId);
  else deleteCookie(SCOPE_COMPANY_COOKIE);

  if (next.branchId) setCookie(SCOPE_BRANCH_COOKIE, next.branchId);
  else deleteCookie(SCOPE_BRANCH_COOKIE);
}

type SelectionState = {
  tenantId?: string;
  companyId?: string;
  branchId?: string;
  cameraId?: string;

  setTenantId: (tenantId?: string) => void;
  setCompanyId: (companyId?: string) => void;
  setBranchId: (branchId?: string) => void;
  setCameraId: (cameraId?: string) => void;

  reset: () => void;
};

export const useSelection = create<SelectionState>()(
  persist(
    (set, get) => ({
      tenantId: undefined,
      companyId: undefined,
      branchId: undefined,
      cameraId: undefined,

      // If tenant changes, dependent selections are invalid.
      setTenantId: (tenantId) => {
        syncScopeCookies({ tenantId, companyId: undefined, branchId: undefined });
        set({ tenantId, companyId: undefined, branchId: undefined, cameraId: undefined });
      },

      // If company changes, branch/camera selection is invalid.
      setCompanyId: (companyId) => {
        syncScopeCookies({ tenantId: get().tenantId, companyId, branchId: undefined });
        set({ companyId, branchId: undefined, cameraId: undefined });
      },

      // If branch changes, camera selection is invalid.
      setBranchId: (branchId) => {
        syncScopeCookies({
          tenantId: get().tenantId,
          companyId: get().companyId,
          branchId,
        });
        set({ branchId, cameraId: undefined });
      },

      setCameraId: (cameraId) => set({ cameraId }),

      reset: () => {
        syncScopeCookies({ tenantId: undefined, companyId: undefined, branchId: undefined });
        set({ tenantId: undefined, companyId: undefined, branchId: undefined, cameraId: undefined });
      },
    }),
    { name: "attendance-admin-selection" }
  )
);
