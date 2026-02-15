"use client";

/**
 * /setup
 *
 * Milestone 1:
 * - Bootstrap a new tenant/company/branch + admin user (optional; dev-friendly)
 * - Create cameras for a selected branch
 *
 * Notes:
 * - "Context" (tenant/company/branch/camera) is persisted in `lib/selection.ts`.
 * - Auth session (JWT tokens + scope) is persisted in `lib/auth.ts`.
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { apiJson } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useSelection } from "@/lib/selection";
import type { CameraListOut, TokenResponse } from "@/lib/types";
import { StorePicker } from "@/components/StorePicker";
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

type BootstrapRequest = {
  tenant_name: string;
  company_name: string;
  branch_name: string;
  branch_code: string;
  timezone: string;
  currency_code: string;
  admin_email: string;
  admin_password: string;
};

export default function SetupPage() {
  const router = useRouter();

  const accessToken = useAuth((s) => s.accessToken);
  const setFromTokenResponse = useAuth((s) => s.setFromTokenResponse);

  const tenantId = useSelection((s) => s.tenantId);
  const companyId = useSelection((s) => s.companyId);
  const branchId = useSelection((s) => s.branchId);
  const cameraId = useSelection((s) => s.cameraId);

  const setTenantId = useSelection((s) => s.setTenantId);
  const setCompanyId = useSelection((s) => s.setCompanyId);
  const setBranchId = useSelection((s) => s.setBranchId);
  const setCameraId = useSelection((s) => s.setCameraId);

  const selectionSummary = useMemo(
    () => ({
      tenantId: tenantId ?? "(none)",
      companyId: companyId ?? "(none)",
      branchId: branchId ?? "(none)",
      cameraId: cameraId ?? "(none)",
    }),
    [tenantId, companyId, branchId, cameraId]
  );

  // ----------------------------
  // 1) Bootstrap (optional)
  // ----------------------------
  const [tenantName, setTenantName] = useState("Demo Tenant");
  const [companyName, setCompanyName] = useState("Demo Company");
  const [branchName, setBranchName] = useState("Riyadh Branch");
  const [branchCode, setBranchCode] = useState("RYD");
  const [timezone, setTimezone] = useState("Asia/Riyadh");
  const [currencyCode, setCurrencyCode] = useState("SAR");
  const [adminEmail, setAdminEmail] = useState("admin@example.com");
  const [adminPassword, setAdminPassword] = useState("admin");

  const bootstrapM = useMutation({
    mutationFn: async () => {
      const payload: BootstrapRequest = {
        tenant_name: tenantName.trim(),
        company_name: companyName.trim(),
        branch_name: branchName.trim(),
        branch_code: branchCode.trim(),
        timezone: timezone.trim() || "UTC",
        currency_code: currencyCode.trim() || "SAR",
        admin_email: adminEmail.trim(),
        admin_password: adminPassword,
      };

      if (!payload.tenant_name) throw new Error("tenant_name is required");
      if (!payload.company_name) throw new Error("company_name is required");
      if (!payload.branch_name) throw new Error("branch_name is required");
      if (!payload.branch_code) throw new Error("branch_code is required");
      if (!payload.admin_email) throw new Error("admin_email is required");
      if (!payload.admin_password) throw new Error("admin_password is required");

      return apiJson<TokenResponse>("/api/v1/bootstrap", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    onSuccess: (t) => {
      setFromTokenResponse(t);

      // Default the client scope/selection from the server-issued scope.
      setTenantId(String(t.scope.tenant_id));
      setCompanyId(t.scope.company_id ? String(t.scope.company_id) : undefined);
      setBranchId(t.scope.branch_id ? String(t.scope.branch_id) : undefined);

      // After bootstrap, user can create cameras / upload videos etc.
      router.push("/dashboard");
    },
  });

  // ----------------------------
  // 2) Create camera (branch-scoped)
  // ----------------------------
  const [cameraName, setCameraName] = useState("");
  const [cameraPlacement, setCameraPlacement] = useState("");

  const createCameraM = useMutation({
    mutationFn: async () => {
      if (!branchId) throw new Error("Select a branch first.");
      if (!cameraName.trim()) throw new Error("Camera name is required.");

      return apiJson<CameraListOut>(`/api/v1/branches/${branchId}/cameras`, {
        method: "POST",
        body: JSON.stringify({
          name: cameraName.trim(),
          placement: cameraPlacement.trim() ? cameraPlacement.trim() : null,
          calibration_json: null,
        }),
      });
    },
    onSuccess: (cam) => {
      setCameraName("");
      setCameraPlacement("");
      setCameraId(cam.id);
    },
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Setup</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Bootstrap tenancy (optional) and manage branch cameras.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Current Context</CardTitle>
          <CardDescription>Tenant/company/branch/camera selection.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-3">
            <StorePicker />
          </div>
          <pre className="overflow-auto rounded-lg bg-muted/30 p-3 text-xs">
            {JSON.stringify(selectionSummary, null, 2)}
          </pre>

          {cameraId ? (
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
          ) : null}
        </CardContent>
      </Card>

      {!accessToken ? (
        <Card>
          <CardHeader>
            <CardTitle>Bootstrap (Optional)</CardTitle>
            <CardDescription>
              Create a new tenant/company/branch and an admin user. This is meant
              for local/dev environments.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1">
                <Label className="text-xs text-muted-foreground">Tenant name</Label>
                <Input value={tenantName} onChange={(e) => setTenantName(e.target.value)} />
              </div>
              <div className="space-y-1">
                <Label className="text-xs text-muted-foreground">Company name</Label>
                <Input value={companyName} onChange={(e) => setCompanyName(e.target.value)} />
              </div>
              <div className="space-y-1">
                <Label className="text-xs text-muted-foreground">Branch name</Label>
                <Input value={branchName} onChange={(e) => setBranchName(e.target.value)} />
              </div>
              <div className="space-y-1">
                <Label className="text-xs text-muted-foreground">Branch code</Label>
                <Input value={branchCode} onChange={(e) => setBranchCode(e.target.value)} />
              </div>
              <div className="space-y-1">
                <Label className="text-xs text-muted-foreground">Timezone</Label>
                <Input value={timezone} onChange={(e) => setTimezone(e.target.value)} />
              </div>
              <div className="space-y-1">
                <Label className="text-xs text-muted-foreground">Currency</Label>
                <Input value={currencyCode} onChange={(e) => setCurrencyCode(e.target.value)} />
              </div>
              <div className="space-y-1">
                <Label className="text-xs text-muted-foreground">Admin email</Label>
                <Input value={adminEmail} onChange={(e) => setAdminEmail(e.target.value)} />
              </div>
              <div className="space-y-1">
                <Label className="text-xs text-muted-foreground">Admin password</Label>
                <Input
                  type="password"
                  value={adminPassword}
                  onChange={(e) => setAdminPassword(e.target.value)}
                />
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <Button type="button" onClick={() => bootstrapM.mutate()} disabled={bootstrapM.isPending}>
                {bootstrapM.isPending ? "Bootstrapping…" : "Bootstrap"}
              </Button>
              {bootstrapM.isError ? (
                <div className="text-sm text-destructive">
                  {bootstrapM.error instanceof Error ? bootstrapM.error.message : String(bootstrapM.error)}
                </div>
              ) : null}
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Create Camera</CardTitle>
            <CardDescription>
              Cameras are branch-scoped. Select a branch above first.
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
                  disabled={!branchId}
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
                  disabled={!branchId}
                />
              </div>
              <div className="flex items-end gap-2 sm:col-span-1">
                <Button
                  type="button"
                  disabled={!branchId || !cameraName.trim() || createCameraM.isPending}
                  onClick={() => createCameraM.mutate()}
                >
                  {createCameraM.isPending ? "Creating…" : "Create"}
                </Button>

                {createCameraM.isError ? (
                  <div className="text-sm text-destructive">
                    {createCameraM.error instanceof Error
                      ? createCameraM.error.message
                      : String(createCameraM.error)}
                  </div>
                ) : null}
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

