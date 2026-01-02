"use client";

/**
 * /setup
 *
 * Seed data UI for the MVP:
 * - create org
 * - create store
 * - create camera (optionally with calibration_json)
 *
 * This mirrors Swagger but is usable by non-technical users.
 */

import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import { apiJson } from "@/lib/api";
import { useSelection } from "@/lib/selection";
import type { CameraListOut, OrganizationOut, StoreOut } from "@/lib/types";

export default function SetupPage() {
  const orgId = useSelection((s) => s.orgId);
  const storeId = useSelection((s) => s.storeId);
  const cameraId = useSelection((s) => s.cameraId);

  const setOrgId = useSelection((s) => s.setOrgId);
  const setStoreId = useSelection((s) => s.setStoreId);
  const setCameraId = useSelection((s) => s.setCameraId);

  // Lists (React Query will cache these across pages)
  const orgsQ = useQuery({
    queryKey: ["orgs"],
    queryFn: () => apiJson<OrganizationOut[]>("/api/v1/organizations"),
  });

  const storesQ = useQuery({
    queryKey: ["stores", orgId],
    enabled: Boolean(orgId),
    queryFn: () => apiJson<StoreOut[]>(`/api/v1/organizations/${orgId}/stores`),
  });

  const camerasQ = useQuery({
    queryKey: ["cameras", storeId],
    enabled: Boolean(storeId),
    queryFn: () =>
      apiJson<CameraListOut[]>(`/api/v1/stores/${storeId}/cameras`),
  });

  // Form state
  const [orgName, setOrgName] = useState("");
  const [storeName, setStoreName] = useState("");
  const [storeTz, setStoreTz] = useState("Asia/Kolkata");
  const [cameraName, setCameraName] = useState("");
  const [cameraPlacement, setCameraPlacement] = useState("");

  // Optional: paste calibration JSON to create camera with calibration immediately
  const [calibrationJsonText, setCalibrationJsonText] = useState("");

  const selectionSummary = useMemo(
    () => ({
      orgId: orgId ?? "(none)",
      storeId: storeId ?? "(none)",
      cameraId: cameraId ?? "(none)",
    }),
    [orgId, storeId, cameraId]
  );

  // Create org
  const createOrg = useMutation({
    mutationFn: async () => {
      if (!orgName.trim()) throw new Error("Org name required");
      return apiJson<OrganizationOut>("/api/v1/organizations", {
        method: "POST",
        body: JSON.stringify({ name: orgName }),
      });
    },
    onSuccess: (org) => {
      setOrgName("");
      setOrgId(org.id); // selecting the new org also clears store/camera automatically
      orgsQ.refetch();
    },
  });

  // Create store
  const createStore = useMutation({
    mutationFn: async () => {
      if (!orgId) throw new Error("Select an organization first");
      if (!storeName.trim()) throw new Error("Store name required");

      return apiJson<StoreOut>(`/api/v1/organizations/${orgId}/stores`, {
        method: "POST",
        body: JSON.stringify({ name: storeName, timezone: storeTz || "UTC" }),
      });
    },
    onSuccess: (store) => {
      setStoreName("");
      setStoreId(store.id);
      storesQ.refetch();
    },
  });

  // Create camera
  const createCamera = useMutation({
    mutationFn: async () => {
      if (!storeId) throw new Error("Select a store first");
      if (!cameraName.trim()) throw new Error("Camera name required");

      // calibration_json is optional, but must be valid JSON if provided.
      let calibration_json: Record<string, unknown> | null = null;
      const trimmed = calibrationJsonText.trim();
      if (trimmed.length > 0) {
        try {
          calibration_json = JSON.parse(trimmed);
        } catch {
          throw new Error("Calibration JSON is not valid JSON");
        }
      }

      return apiJson<CameraListOut>(`/api/v1/stores/${storeId}/cameras`, {
        method: "POST",
        body: JSON.stringify({
          name: cameraName,
          placement: cameraPlacement || null,
          calibration_json,
        }),
      });
    },
    onSuccess: (cam) => {
      setCameraName("");
      setCameraPlacement("");
      setCameraId(cam.id);
      camerasQ.refetch();
    },
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Setup</h1>

      <div className="rounded border bg-white p-4 text-sm">
        <div className="mb-2 font-medium">Current selection</div>
        <pre className="overflow-auto">
          {JSON.stringify(selectionSummary, null, 2)}
        </pre>
      </div>

      {/* Organizations */}
      <section className="rounded border bg-white p-4">
        <h2 className="text-lg font-medium">Organizations</h2>

        <div className="mt-3 flex flex-wrap items-end gap-2">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-500">Create org</label>
            <input
              className="w-72 rounded border px-2 py-1"
              value={orgName}
              onChange={(e) => setOrgName(e.target.value)}
              placeholder="e.g. Sakarwala Retail"
            />
          </div>

          <button
            className="rounded bg-black px-3 py-2 text-white disabled:opacity-50"
            disabled={!orgName.trim() || createOrg.isPending}
            onClick={() => createOrg.mutate()}
          >
            {createOrg.isPending ? "Creating…" : "Create"}
          </button>

          {createOrg.isError && (
            <div className="text-red-600">{String(createOrg.error)}</div>
          )}
        </div>

        <div className="mt-4 flex flex-col gap-2">
          <label className="text-xs text-gray-500">Select org</label>
          <select
            className="w-96 rounded border px-2 py-1"
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
        </div>
      </section>

      {/* Stores */}
      <section className="rounded border bg-white p-4">
        <h2 className="text-lg font-medium">Stores</h2>

        <div className="mt-3 flex flex-wrap items-end gap-2">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-500">Create store</label>
            <input
              className="w-72 rounded border px-2 py-1"
              value={storeName}
              onChange={(e) => setStoreName(e.target.value)}
              placeholder="e.g. Store 1 - Pune"
              disabled={!orgId}
            />
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-500">Timezone</label>
            <input
              className="w-56 rounded border px-2 py-1"
              value={storeTz}
              onChange={(e) => setStoreTz(e.target.value)}
              placeholder="Asia/Kolkata"
              disabled={!orgId}
            />
          </div>

          <button
            className="rounded bg-black px-3 py-2 text-white disabled:opacity-50"
            disabled={!orgId || !storeName.trim() || createStore.isPending}
            onClick={() => createStore.mutate()}
          >
            {createStore.isPending ? "Creating…" : "Create"}
          </button>

          {createStore.isError && (
            <div className="text-red-600">{String(createStore.error)}</div>
          )}
        </div>

        <div className="mt-4 flex flex-col gap-2">
          <label className="text-xs text-gray-500">Select store</label>
          <select
            className="w-96 rounded border px-2 py-1"
            value={storeId ?? ""}
            disabled={!orgId}
            onChange={(e) => setStoreId(e.target.value || undefined)}
          >
            <option value="">Select store…</option>
            {(storesQ.data ?? []).map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} ({s.timezone})
              </option>
            ))}
          </select>
        </div>
      </section>

      {/* Cameras */}
      <section className="rounded border bg-white p-4">
        <h2 className="text-lg font-medium">Cameras</h2>

        <div className="mt-3 grid gap-3">
          <div className="flex flex-wrap items-end gap-2">
            <div className="flex flex-col gap-1">
              <label className="text-xs text-gray-500">Camera name</label>
              <input
                className="w-72 rounded border px-2 py-1"
                value={cameraName}
                onChange={(e) => setCameraName(e.target.value)}
                placeholder="e.g. Entrance CCTV"
                disabled={!storeId}
              />
            </div>

            <div className="flex flex-col gap-1">
              <label className="text-xs text-gray-500">
                Placement (optional)
              </label>
              <input
                className="w-72 rounded border px-2 py-1"
                value={cameraPlacement}
                onChange={(e) => setCameraPlacement(e.target.value)}
                placeholder="e.g. Door top-left"
                disabled={!storeId}
              />
            </div>

            <button
              className="rounded bg-black px-3 py-2 text-white disabled:opacity-50"
              disabled={
                !storeId || !cameraName.trim() || createCamera.isPending
              }
              onClick={() => createCamera.mutate()}
            >
              {createCamera.isPending ? "Creating…" : "Create"}
            </button>

            {createCamera.isError && (
              <div className="text-red-600">{String(createCamera.error)}</div>
            )}
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-500">
              Calibration JSON (optional; paste raw JSON)
            </label>
            <textarea
              className="min-h-[140px] w-full rounded border px-2 py-1 font-mono text-xs"
              value={calibrationJsonText}
              onChange={(e) => setCalibrationJsonText(e.target.value)}
              placeholder='{"coord_space":"normalized","door_roi_polygon":[...], ... }'
              disabled={!storeId}
            />
          </div>

          <div className="flex flex-col gap-2">
            <label className="text-xs text-gray-500">Select camera</label>
            <select
              className="w-96 rounded border px-2 py-1"
              value={cameraId ?? ""}
              disabled={!storeId}
              onChange={(e) => setCameraId(e.target.value || undefined)}
            >
              <option value="">Select camera…</option>
              {(camerasQ.data ?? []).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
        </div>
      </section>
    </div>
  );
}
