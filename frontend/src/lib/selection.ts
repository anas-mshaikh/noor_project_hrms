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
    (set) => ({
      tenantId: undefined,
      companyId: undefined,
      branchId: undefined,
      cameraId: undefined,

      // If tenant changes, dependent selections are invalid.
      setTenantId: (tenantId) =>
        set({ tenantId, companyId: undefined, branchId: undefined, cameraId: undefined }),

      // If company changes, branch/camera selection is invalid.
      setCompanyId: (companyId) => set({ companyId, branchId: undefined, cameraId: undefined }),

      // If branch changes, camera selection is invalid.
      setBranchId: (branchId) => set({ branchId, cameraId: undefined }),

      setCameraId: (cameraId) => set({ cameraId }),

      reset: () =>
        set({ tenantId: undefined, companyId: undefined, branchId: undefined, cameraId: undefined }),
    }),
    { name: "attendance-admin-selection" }
  )
);
