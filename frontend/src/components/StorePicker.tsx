"use client";

/**
 * components/StorePicker.tsx
 *
 * Dropdowns:
 *   Organization -> Store -> Camera
 *
 * Backend endpoints used:
 * - GET /api/v1/organizations
 * - GET /api/v1/organizations/{org_id}/stores
 * - GET /api/v1/stores/{store_id}/cameras
 *
 * Selection is persisted via Zustand in lib/selection.ts.
 */

import { useQuery } from "@tanstack/react-query";

import { apiJson } from "@/lib/api";
import { useSelection } from "@/lib/selection";
import type { CameraListOut, OrganizationOut, StoreOut } from "@/lib/types";

export function StorePicker() {
  const orgId = useSelection((s) => s.orgId);
  const storeId = useSelection((s) => s.storeId);
  const cameraId = useSelection((s) => s.cameraId);

  const setOrgId = useSelection((s) => s.setOrgId);
  const setStoreId = useSelection((s) => s.setStoreId);
  const setCameraId = useSelection((s) => s.setCameraId);

  const orgsQ = useQuery({
    queryKey: ["orgs"],
    queryFn: () => apiJson<OrganizationOut[]>("/api/v1/organizations"),
  });

  const storesQ = useQuery({
    queryKey: ["stores", orgId],
    enabled: Boolean(orgId), // don't fetch until org is selected
    queryFn: () => apiJson<StoreOut[]>(`/api/v1/organizations/${orgId}/stores`),
  });

  const camerasQ = useQuery({
    queryKey: ["cameras", storeId],
    enabled: Boolean(storeId), // don't fetch until store is selected
    queryFn: () =>
      apiJson<CameraListOut[]>(`/api/v1/stores/${storeId}/cameras`),
  });

  return (
    <div className="flex flex-wrap items-end gap-2 text-sm">
      <div className="flex flex-col gap-1">
        <label className="text-xs text-gray-500">Org</label>
        <select
          className="w-56 rounded border px-2 py-1"
          value={orgId ?? ""}
          onChange={(e) => setOrgId(e.target.value || undefined)}
        >
          <option value="">Select org…</option>
          {(orgsQ.data ?? []).map((o) => (
            <option key={o.id} value={o.id}>
              {o.name}
            </option>
          ))}
        </select>
        {orgsQ.isError && (
          <div className="text-xs text-red-600">Failed to load orgs</div>
        )}
      </div>

      <div className="flex flex-col gap-1">
        <label className="text-xs text-gray-500">Store</label>
        <select
          className="w-56 rounded border px-2 py-1"
          value={storeId ?? ""}
          disabled={!orgId}
          onChange={(e) => setStoreId(e.target.value || undefined)}
        >
          <option value="">
            {orgId ? "Select store…" : "Select org first"}
          </option>
          {(storesQ.data ?? []).map((s) => (
            <option key={s.id} value={s.id}>
              {s.name} ({s.timezone})
            </option>
          ))}
        </select>
        {storesQ.isError && (
          <div className="text-xs text-red-600">Failed to load stores</div>
        )}
      </div>

      <div className="flex flex-col gap-1">
        <label className="text-xs text-gray-500">Camera</label>
        <select
          className="w-56 rounded border px-2 py-1"
          value={cameraId ?? ""}
          disabled={!storeId}
          onChange={(e) => setCameraId(e.target.value || undefined)}
        >
          <option value="">
            {storeId ? "Select camera…" : "Select store first"}
          </option>
          {(camerasQ.data ?? []).map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
        {camerasQ.isError && (
          <div className="text-xs text-red-600">Failed to load cameras</div>
        )}
      </div>
    </div>
  );
}
