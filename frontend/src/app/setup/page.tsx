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
import Link from "next/link";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

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
  // const [calibrationJsonText, setCalibrationJsonText] = useState("");

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

      // // calibration_json is optional, but must be valid JSON if provided.
      // let calibration_json: Record<string, unknown> | null = null;
      // const trimmed = calibrationJsonText.trim();
      // if (trimmed.length > 0) {
      //   try {
      //     calibration_json = JSON.parse(trimmed);
      //   } catch {
      //     throw new Error("Calibration JSON is not valid JSON");
      //   }
      // }

      return apiJson<CameraListOut>(`/api/v1/stores/${storeId}/cameras`, {
        method: "POST",
        body: JSON.stringify({
          name: cameraName,
          placement: cameraPlacement || null,
          calibration_json: null,
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
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Setup</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Create an org → store → camera, then calibrate the door zones/line.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Current Selection</CardTitle>
          <CardDescription>Debug view (safe to remove later).</CardDescription>
        </CardHeader>
        <CardContent>
          <pre className="overflow-auto rounded-lg bg-muted/30 p-3 text-xs">
            {JSON.stringify(selectionSummary, null, 2)}
          </pre>
        </CardContent>
      </Card>

      {/* Organizations */}
      <Card>
        <CardHeader>
          <CardTitle>Organizations</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1">
              <Label className="text-xs text-muted-foreground">Create org</Label>
              <Input
                value={orgName}
                onChange={(e) => setOrgName(e.target.value)}
                placeholder="e.g. Sakarwala Retail"
              />
            </div>

            <div className="flex items-end gap-2">
              <Button
                type="button"
                disabled={!orgName.trim() || createOrg.isPending}
                onClick={() => createOrg.mutate()}
              >
                {createOrg.isPending ? "Creating…" : "Create"}
              </Button>

              {createOrg.isError && (
                <div className="text-sm text-destructive">
                  {String(createOrg.error)}
                </div>
              )}
            </div>
          </div>

          <div className="space-y-1">
            <Label className="text-xs text-muted-foreground">Select org</Label>
            <select
              className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
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
        </CardContent>
      </Card>

      {/* Stores */}
      <Card>
        <CardHeader>
          <CardTitle>Stores</CardTitle>
          <CardDescription>Stores belong to an organization.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="space-y-1 sm:col-span-1">
              <Label className="text-xs text-muted-foreground">Create store</Label>
              <Input
                value={storeName}
                onChange={(e) => setStoreName(e.target.value)}
                placeholder="e.g. Dariyapur"
                disabled={!orgId}
              />
            </div>

            <div className="space-y-1 sm:col-span-1">
              <Label className="text-xs text-muted-foreground">Timezone</Label>
              <Input
                value={storeTz}
                onChange={(e) => setStoreTz(e.target.value)}
                placeholder="Asia/Kolkata"
                disabled={!orgId}
              />
            </div>

            <div className="flex items-end gap-2 sm:col-span-1">
              <Button
                type="button"
                disabled={!orgId || !storeName.trim() || createStore.isPending}
                onClick={() => createStore.mutate()}
              >
                {createStore.isPending ? "Creating…" : "Create"}
              </Button>

              {createStore.isError && (
                <div className="text-sm text-destructive">
                  {String(createStore.error)}
                </div>
              )}
            </div>
          </div>

          <div className="space-y-1">
            <Label className="text-xs text-muted-foreground">Select store</Label>
            <select
              className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
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
        </CardContent>
      </Card>

      {/* Cameras */}
      <Card>
        <CardHeader>
          <CardTitle>Cameras</CardTitle>
          <CardDescription>
            Create a camera for the selected store, then calibrate it.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="space-y-1 sm:col-span-1">
              <Label className="text-xs text-muted-foreground">Camera name</Label>
              <Input
                value={cameraName}
                onChange={(e) => setCameraName(e.target.value)}
                placeholder="e.g. Entrance"
                disabled={!storeId}
              />
            </div>

            <div className="space-y-1 sm:col-span-1">
              <Label className="text-xs text-muted-foreground">
                Placement (optional)
              </Label>
              <Input
                value={cameraPlacement}
                onChange={(e) => setCameraPlacement(e.target.value)}
                placeholder="e.g. Door top-left"
                disabled={!storeId}
              />
            </div>

            <div className="flex items-end gap-2 sm:col-span-1">
              <Button
                type="button"
                disabled={!storeId || !cameraName.trim() || createCamera.isPending}
                onClick={() => createCamera.mutate()}
              >
                {createCamera.isPending ? "Creating…" : "Create"}
              </Button>

              {createCamera.isError && (
                <div className="text-sm text-destructive">
                  {String(createCamera.error)}
                </div>
              )}
            </div>
          </div>

          {/* <div className="flex flex-col gap-1">
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
          </div> */}

          {cameraId && (
            <div className="flex flex-wrap items-center gap-2">
              <div className="text-xs text-muted-foreground">
                Calibration is required before running jobs.
              </div>

              <Button asChild variant="outline">
                <Link href={`/cameras/${cameraId}/calibration`}>
                  Calibrate this camera
                </Link>
              </Button>
            </div>
          )}

          <div className="space-y-1">
            <Label className="text-xs text-muted-foreground">Select camera</Label>
            <select
              className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
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
        </CardContent>
      </Card>
    </div>
  );
}
