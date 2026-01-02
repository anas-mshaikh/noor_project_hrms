"use client";

/**
 * lib/selection.ts
 *
 * Persist org/store/camera selection in localStorage.
 *
 * IMPORTANT: "use client" is required because Zustand persist uses localStorage,
 * which does not exist on the server.
 */

import { create } from "zustand";
import { persist } from "zustand/middleware";

type SelectionState = {
  orgId?: string;
  storeId?: string;
  cameraId?: string;

  setOrgId: (orgId?: string) => void;
  setStoreId: (storeId?: string) => void;
  setCameraId: (cameraId?: string) => void;

  reset: () => void;
};

export const useSelection = create<SelectionState>()(
  persist(
    (set) => ({
      orgId: undefined,
      storeId: undefined,
      cameraId: undefined,

      // If org changes, dependent selections are invalid.
      setOrgId: (orgId) =>
        set({ orgId, storeId: undefined, cameraId: undefined }),

      // If store changes, camera selection is invalid.
      setStoreId: (storeId) => set({ storeId, cameraId: undefined }),

      setCameraId: (cameraId) => set({ cameraId }),

      reset: () =>
        set({ orgId: undefined, storeId: undefined, cameraId: undefined }),
    }),
    { name: "attendance-admin-selection" }
  )
);
