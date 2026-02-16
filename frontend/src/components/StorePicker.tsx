"use client";

/**
 * components/StorePicker.tsx
 *
 * Dropdowns:
 *   Tenant -> Company -> Branch -> Camera
 *
 * Backend endpoints used:
 * - GET /api/v1/tenancy/companies
 * - GET /api/v1/tenancy/branches?company_id=...
 * - GET /api/v1/branches/{branch_id}/cameras
 *
 * Selection is persisted via Zustand in lib/selection.ts.
 */

import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "@/lib/i18n";

import { apiJson } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useSelection } from "@/lib/selection";
import type { BranchOut, CameraListOut, CompanyOut } from "@/lib/types";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

export function StorePicker() {
  const { t } = useTranslation();
  const authScope = useAuth((s) => s.scope);

  const tenantId = useSelection((s) => s.tenantId);
  const companyId = useSelection((s) => s.companyId);
  const branchId = useSelection((s) => s.branchId);
  const cameraId = useSelection((s) => s.cameraId);

  const setTenantId = useSelection((s) => s.setTenantId);
  const setCompanyId = useSelection((s) => s.setCompanyId);
  const setBranchId = useSelection((s) => s.setBranchId);
  const setCameraId = useSelection((s) => s.setCameraId);

  // If the user is already authenticated, default the selection state to the token scope.
  // This keeps API headers consistent even if localStorage selection was cleared.
  useEffect(() => {
    if (!authScope) return;
    if (!tenantId) setTenantId(String(authScope.tenant_id));
    if (!companyId && authScope.company_id) setCompanyId(String(authScope.company_id));
    if (!branchId && authScope.branch_id) setBranchId(String(authScope.branch_id));
    // cameraId has no server-side "default"; keep it user-selected.
  }, [authScope, tenantId, companyId, branchId, setTenantId, setCompanyId, setBranchId]);

  const allowedTenantIds = authScope?.allowed_tenant_ids ?? [];

  const companiesQ = useQuery({
    queryKey: ["companies", tenantId],
    enabled: Boolean(tenantId),
    queryFn: () => apiJson<CompanyOut[]>("/api/v1/tenancy/companies"),
  });

  const branchesQ = useQuery({
    queryKey: ["branches", tenantId, companyId],
    enabled: Boolean(tenantId && companyId),
    queryFn: () =>
      apiJson<BranchOut[]>(
        `/api/v1/tenancy/branches?company_id=${encodeURIComponent(companyId as string)}`
      ),
  });

  const camerasQ = useQuery({
    queryKey: ["cameras", tenantId, branchId],
    enabled: Boolean(tenantId && branchId),
    queryFn: () => apiJson<CameraListOut[]>(`/api/v1/branches/${branchId}/cameras`),
  });

  const selectClassName = cn(
    "h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm",
    "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
    "disabled:cursor-not-allowed disabled:opacity-50"
  );

  return (
    <div className="grid gap-2 text-sm sm:grid-cols-2 md:grid-cols-4">
      <div className="flex flex-col gap-1">
        <Label className="text-xs text-muted-foreground">
          {t("picker.tenant", { defaultValue: "Tenant" })}
        </Label>
        <select
          className={selectClassName}
          value={tenantId ?? ""}
          disabled={allowedTenantIds.length <= 1}
          onChange={(e) => setTenantId(e.target.value || undefined)}
        >
          <option value="">
            {t("picker.select_tenant", { defaultValue: "Select tenant..." })}
          </option>
          {(allowedTenantIds.length ? allowedTenantIds : tenantId ? [tenantId] : []).map((id) => (
            <option key={id} value={id}>
              {id}
            </option>
          ))}
        </select>
        {allowedTenantIds.length > 1 && !tenantId ? (
          <div className="text-xs text-muted-foreground">
            {t("picker.tenant_required", {
              defaultValue: "Required for multi-tenant users.",
            })}
          </div>
        ) : null}
      </div>

      <div className="flex flex-col gap-1">
        <Label className="text-xs text-muted-foreground">
          {t("picker.company", { defaultValue: "Company" })}
        </Label>
        <select
          className={selectClassName}
          value={companyId ?? ""}
          disabled={!tenantId || companiesQ.isPending}
          onChange={(e) => setCompanyId(e.target.value || undefined)}
        >
          <option value="">
            {tenantId
              ? t("picker.select_company", { defaultValue: "Select company..." })
              : t("picker.select_tenant_first", { defaultValue: "Select tenant first" })}
          </option>
          {companiesQ.isPending && (
            <option>{t("common.loading", { defaultValue: "Loading..." })}</option>
          )}
          {(companiesQ.data ?? []).map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
        {companiesQ.isError ? (
          <div className="text-xs text-destructive">
            {t("picker.failed_companies", { defaultValue: "Failed to load companies" })}
          </div>
        ) : null}
      </div>

      <div className="flex flex-col gap-1">
        <Label className="text-xs text-muted-foreground">
          {t("picker.branch", { defaultValue: "Branch" })}
        </Label>
        <select
          className={selectClassName}
          value={branchId ?? ""}
          disabled={!tenantId || !companyId || branchesQ.isPending}
          onChange={(e) => setBranchId(e.target.value || undefined)}
        >
          <option value="">
            {companyId
              ? t("picker.select_branch", { defaultValue: "Select branch..." })
              : t("picker.select_company_first", { defaultValue: "Select company first" })}
          </option>
          {branchesQ.isPending && (
            <option>{t("common.loading", { defaultValue: "Loading..." })}</option>
          )}
          {(branchesQ.data ?? []).map((b) => (
            <option key={b.id} value={b.id}>
              {b.name} ({b.code})
            </option>
          ))}
        </select>
        {branchesQ.isError ? (
          <div className="text-xs text-destructive">
            {t("picker.failed_branches", { defaultValue: "Failed to load branches" })}
          </div>
        ) : null}
      </div>

      <div className="flex flex-col gap-1">
        <Label className="text-xs text-muted-foreground">
          {t("picker.camera", { defaultValue: "Camera" })}
        </Label>
        <select
          className={selectClassName}
          value={cameraId ?? ""}
          disabled={!tenantId || !branchId || camerasQ.isPending}
          onChange={(e) => setCameraId(e.target.value || undefined)}
        >
          <option value="">
            {branchId
              ? t("picker.select_camera", { defaultValue: "Select camera..." })
              : t("picker.select_branch_first", { defaultValue: "Select branch first" })}
          </option>
          {camerasQ.isPending && (
            <option>{t("common.loading", { defaultValue: "Loading..." })}</option>
          )}
          {(camerasQ.data ?? []).map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
        {camerasQ.isError ? (
          <div className="text-xs text-destructive">
            {t("picker.failed_cameras", { defaultValue: "Failed to load cameras" })}
          </div>
        ) : null}
      </div>
    </div>
  );
}
