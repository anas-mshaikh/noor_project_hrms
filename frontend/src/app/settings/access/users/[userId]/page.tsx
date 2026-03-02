"use client";

import * as React from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/lib/auth";
import { parseUuidParam } from "@/lib/guards";
import { cn } from "@/lib/utils";
import { toastApiError } from "@/lib/toastApiError";
import type {
  BranchOut,
  CompanyOut,
  IamUserPatchIn,
  RoleOut,
  UserRoleOut,
  UUID,
} from "@/lib/types";
import { listBranches, listCompanies } from "@/features/tenancy/api/tenancy";
import { tenancyKeys } from "@/features/tenancy/queryKeys";
import {
  assignUserRole,
  getUser,
  listRoles,
  listUserRoles,
  patchUser,
  removeUserRole,
} from "@/features/iam/api/iam";
import { iamKeys } from "@/features/iam/queryKeys";
import {
  buildRoleAssignIn,
  type RoleScopeKind,
  validateRoleAssignmentInput,
} from "@/features/iam/roleAssignment";

import { DataTable } from "@/components/ds/DataTable";
import { DSCard } from "@/components/ds/DSCard";
import { EmptyState } from "@/components/ds/EmptyState";
import { ErrorState } from "@/components/ds/ErrorState";
import { PageHeader } from "@/components/ds/PageHeader";
import { RightPanelStack } from "@/components/ds/RightPanelStack";
import { EntityProfileTemplate } from "@/components/ds/templates/EntityProfileTemplate";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

function formatDateTime(value: string): string {
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

function scopeLabel(r: UserRoleOut): string {
  if (r.company_id && r.branch_id) return "Branch";
  if (r.company_id) return "Company";
  return "Tenant";
}

export default function UserDetailPage({ params }: { params: { userId?: string } }) {
  // In production builds, using `useParams()` is the most reliable way to read dynamic
  // route segments from a client component.
  const routeParams = useParams() as { userId?: string | string[] };
  const userIdRaw =
    (Array.isArray(routeParams.userId) ? routeParams.userId[0] : routeParams.userId) ??
    params?.userId ??
    null;
  const userId = parseUuidParam(userIdRaw);
  const canLoad = Boolean(userId);

  const permissions = useAuth((s) => s.permissions);
  const permSet = React.useMemo(() => new Set(permissions ?? []), [permissions]);
  const canWriteUser = permSet.has("iam:user:write");
  const canAssignRole = permSet.has("iam:role:assign");
  const canReadTenancy = permSet.has("tenancy:read") || permSet.has("tenancy:write");

  const qc = useQueryClient();

  const userQ = useQuery({
    queryKey: iamKeys.user(userId),
    enabled: canLoad,
    queryFn: () => {
      if (!userId) throw new Error("Missing user id");
      return getUser(userId);
    },
  });

  const rolesQ = useQuery({
    queryKey: iamKeys.userRoles(userId),
    enabled: canLoad,
    queryFn: () => {
      if (!userId) throw new Error("Missing user id");
      return listUserRoles(userId);
    },
  });

  const rolesCatalogQ = useQuery({
    queryKey: iamKeys.roles(),
    enabled: canLoad,
    queryFn: () => listRoles(),
  });

  const companiesQ = useQuery({
    queryKey: tenancyKeys.companies(),
    enabled: canLoad && canReadTenancy,
    queryFn: () => listCompanies(),
  });

  const companies = (companiesQ.data ?? []) as CompanyOut[];

  const user = userQ.data;
  const assignments = ((rolesQ.data ?? []) as UserRoleOut[]).slice().sort((a, b) => {
    // Newest first for admin readability.
    return String(b.created_at).localeCompare(String(a.created_at));
  });
  const rolesCatalog = (rolesCatalogQ.data ?? []) as RoleOut[];

  const [tab, setTab] = React.useState("overview");

  // ----------------------------
  // Overview patch (phone/status)
  // ----------------------------
  const [phone, setPhone] = React.useState("");
  const [status, setStatus] = React.useState<"ACTIVE" | "DISABLED">("ACTIVE");

  React.useEffect(() => {
    if (!user) return;
    setPhone(user.phone ?? "");
    setStatus(user.status === "DISABLED" ? "DISABLED" : "ACTIVE");
  }, [user]);

  const patchM = useMutation({
    mutationFn: async () => {
      if (!userId) throw new Error("Missing user id");
      const payload: IamUserPatchIn = {
        phone: phone.trim() ? phone.trim() : null,
        status,
      };
      return patchUser(userId, payload);
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: iamKeys.user(userId) });
    },
    onError: (err) => toastApiError(err),
  });

  // ----------------------------
  // Assign role (sheet)
  // ----------------------------
  const [assignOpen, setAssignOpen] = React.useState(false);
  const [roleCode, setRoleCode] = React.useState("");
  const [scopeKind, setScopeKind] = React.useState<RoleScopeKind>("TENANT");
  const [scopeCompanyId, setScopeCompanyId] = React.useState<UUID | "">("");
  const [scopeBranchId, setScopeBranchId] = React.useState<UUID | "">("");
  const [assignError, setAssignError] = React.useState<string | null>(null);

  const branchesQ = useQuery({
    queryKey: tenancyKeys.branches(scopeCompanyId || null),
    enabled: canLoad && canReadTenancy && Boolean(scopeCompanyId),
    queryFn: () => listBranches({ companyId: scopeCompanyId || null }),
  });
  const branches = (branchesQ.data ?? []) as BranchOut[];

  const assignM = useMutation({
    mutationFn: async () => {
      if (!userId) throw new Error("Missing user id");
      setAssignError(null);
      const err = validateRoleAssignmentInput({
        roleCode,
        scopeKind,
        companyId: scopeCompanyId || null,
        branchId: scopeBranchId || null,
      });
      if (err) {
        setAssignError(err);
        throw new Error(err);
      }

      const payload = buildRoleAssignIn({
        roleCode,
        scopeKind,
        companyId: scopeCompanyId || null,
        branchId: scopeBranchId || null,
      });
      return assignUserRole(userId, payload);
    },
    onSuccess: async () => {
      setAssignOpen(false);
      setRoleCode("");
      setScopeKind("TENANT");
      setScopeCompanyId("");
      setScopeBranchId("");
      await qc.invalidateQueries({ queryKey: iamKeys.userRoles(userId) });
    },
    onError: (err) => {
      // Validation errors are already rendered inline; only toast API errors.
      if (err instanceof Error) {
        const msg = err.message;
        if (
          msg === "Role is required." ||
          msg === "Company is required." ||
          msg === "Branch is required." ||
          msg === "Invalid scope."
        ) {
          return;
        }
      }
      toastApiError(err);
    },
  });

  // ----------------------------
  // Remove role (confirm dialog)
  // ----------------------------
  const [removeOpen, setRemoveOpen] = React.useState(false);
  const [removeTarget, setRemoveTarget] = React.useState<UserRoleOut | null>(null);

  const removeM = useMutation({
    mutationFn: async () => {
      if (!userId) throw new Error("Missing user id");
      if (!removeTarget) throw new Error("No role selected.");
      return removeUserRole(userId, {
        roleCode: removeTarget.role_code,
        companyId: removeTarget.company_id,
        branchId: removeTarget.branch_id,
      });
    },
    onSuccess: async () => {
      setRemoveOpen(false);
      setRemoveTarget(null);
      await qc.invalidateQueries({ queryKey: iamKeys.userRoles(userId) });
    },
    onError: (err) => toastApiError(err),
  });

  const selectClassName = cn(
    "h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm",
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
    "disabled:cursor-not-allowed disabled:opacity-50"
  );

  if (!userIdRaw) {
    return (
      <ErrorState
        title="Missing user id"
        error={new Error("Open a user from the Users list.")}
        details={
          <Button asChild variant="outline">
            <Link href="/settings/access/users">Back to users</Link>
          </Button>
        }
      />
    );
  }

  if (!userId) {
    return (
      <ErrorState
        title="Invalid user id"
        error={new Error(`Got: ${String(userIdRaw)}`)}
        details={
          <Button asChild variant="outline">
            <Link href="/settings/access/users">Back to users</Link>
          </Button>
        }
      />
    );
  }

  if (userQ.error) {
    return <ErrorState title="Could not load user" error={userQ.error} onRetry={userQ.refetch} />;
  }

  return (
    <>
      <EntityProfileTemplate
        header={
          <PageHeader
            title={user ? user.email : "User"}
            subtitle={user ? `User ID: ${user.id}` : `User ID: ${userId}`}
            actions={
              <Button asChild variant="outline">
                <Link href="/settings/access/users">Back</Link>
              </Button>
            }
          />
        }
        main={
          <Tabs value={tab} onValueChange={setTab}>
            <TabsList>
              <TabsTrigger value="overview">Overview</TabsTrigger>
              <TabsTrigger value="roles">Role assignments</TabsTrigger>
              <TabsTrigger value="access">Effective access</TabsTrigger>
            </TabsList>

            <TabsContent value="overview">
            <DSCard surface="card" className="p-[var(--ds-space-20)]">
              {userQ.isLoading || !user ? (
                <div className="text-sm text-text-2">Loading...</div>
              ) : (
                <div className="space-y-5">
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="space-y-1">
                      <div className="text-xs text-text-2">Email</div>
                      <div className="text-sm font-medium text-text-1">{user.email}</div>
                    </div>
                    <div className="space-y-1">
                      <div className="text-xs text-text-2">Created</div>
                      <div className="text-sm text-text-1">{formatDateTime(user.created_at)}</div>
                    </div>
                  </div>

                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="space-y-1">
                      <Label htmlFor="user-phone-edit" className="text-xs text-text-2">
                        Phone
                      </Label>
                      <Input
                        id="user-phone-edit"
                        value={phone}
                        onChange={(e) => setPhone(e.target.value)}
                        disabled={!canWriteUser}
                      />
                    </div>
                    <div className="space-y-1">
                      <Label htmlFor="user-status-edit" className="text-xs text-text-2">
                        Status
                      </Label>
                      <select
                        id="user-status-edit"
                        className={selectClassName}
                        value={status}
                        onChange={(e) => setStatus(e.target.value as "ACTIVE" | "DISABLED")}
                        disabled={!canWriteUser}
                      >
                        <option value="ACTIVE">ACTIVE</option>
                        <option value="DISABLED">DISABLED</option>
                      </select>
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    <Button
                      type="button"
                      disabled={!canWriteUser || patchM.isPending}
                      onClick={() => patchM.mutate()}
                    >
                      {patchM.isPending ? "Saving..." : "Save"}
                    </Button>
                    <div className="text-xs text-text-2">
                      Disabling a user revokes refresh tokens.
                    </div>
                  </div>
                </div>
              )}
            </DSCard>
            </TabsContent>

            <TabsContent value="roles">
            <DataTable
              toolbar={
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="text-sm text-text-2">
                    Assign roles with tenant/company/branch scope.
                  </div>
                  <Sheet open={assignOpen} onOpenChange={setAssignOpen}>
                    <SheetTrigger asChild>
                      <Button type="button" disabled={!canAssignRole}>
                        Add role
                      </Button>
                    </SheetTrigger>
                    <SheetContent className="border-border-subtle bg-surface-2 backdrop-blur-xl">
                      <SheetHeader>
                        <SheetTitle>Add role assignment</SheetTitle>
                        <SheetDescription>
                          Choose role and scope. Branch scope requires both company and branch.
                        </SheetDescription>
                      </SheetHeader>

                      <div className="space-y-4 px-4">
                        <div className="space-y-1">
                          <Label htmlFor="assign-role" className="text-xs text-text-2">
                            Role
                          </Label>
                          <select
                            id="assign-role"
                            className={selectClassName}
                            value={roleCode}
                            onChange={(e) => setRoleCode(e.target.value)}
                            disabled={rolesCatalogQ.isLoading || !canAssignRole}
                          >
                            <option value="">Select role...</option>
                            {rolesCatalog.map((r) => (
                              <option key={r.code} value={r.code}>
                                {r.code} — {r.name}
                              </option>
                            ))}
                          </select>
                        </div>

                        <div className="space-y-1">
                          <Label htmlFor="assign-scope" className="text-xs text-text-2">
                            Scope
                          </Label>
                          <select
                            id="assign-scope"
                            className={selectClassName}
                            value={scopeKind}
                            onChange={(e) => {
                              const next = e.target.value as RoleScopeKind;
                              setScopeKind(next);
                              setAssignError(null);
                              // reset dependent fields
                              if (next === "TENANT") {
                                setScopeCompanyId("");
                                setScopeBranchId("");
                              } else if (next === "COMPANY") {
                                setScopeBranchId("");
                              }
                            }}
                            disabled={!canAssignRole}
                          >
                            <option value="TENANT">Tenant</option>
                            <option value="COMPANY">Company</option>
                            <option value="BRANCH">Branch</option>
                          </select>
                        </div>

                        {scopeKind !== "TENANT" ? (
                          canReadTenancy ? (
                            <div className="space-y-4">
                              <div className="space-y-1">
                                <Label htmlFor="assign-company" className="text-xs text-text-2">
                                  Company
                                </Label>
                                <select
                                  id="assign-company"
                                  className={selectClassName}
                                  value={scopeCompanyId}
                                  onChange={(e) => {
                                    setScopeCompanyId((e.target.value as UUID) || "");
                                    setScopeBranchId("");
                                  }}
                                  disabled={companiesQ.isLoading || !canAssignRole}
                                >
                                  <option value="">Select company...</option>
                                  {companies.map((c) => (
                                    <option key={c.id} value={c.id}>
                                      {c.name}
                                    </option>
                                  ))}
                                </select>
                              </div>

                              {scopeKind === "BRANCH" ? (
                                <div className="space-y-1">
                                  <Label htmlFor="assign-branch" className="text-xs text-text-2">
                                    Branch
                                  </Label>
                                  <select
                                    id="assign-branch"
                                    className={selectClassName}
                                    value={scopeBranchId}
                                    onChange={(e) => setScopeBranchId((e.target.value as UUID) || "")}
                                    disabled={!scopeCompanyId || branchesQ.isLoading || !canAssignRole}
                                  >
                                    <option value="">Select branch...</option>
                                    {branches.map((b) => (
                                      <option key={b.id} value={b.id}>
                                        {b.name} ({b.code})
                                      </option>
                                    ))}
                                  </select>
                                </div>
                              ) : null}
                            </div>
                          ) : (
                            <div className="space-y-4">
                              <div className="space-y-1">
                                <Label htmlFor="assign-company-uuid" className="text-xs text-text-2">
                                  Company ID
                                </Label>
                                <Input
                                  id="assign-company-uuid"
                                  value={scopeCompanyId}
                                  onChange={(e) => setScopeCompanyId(e.target.value as UUID)}
                                  placeholder="UUID"
                                  disabled={!canAssignRole}
                                />
                              </div>
                              {scopeKind === "BRANCH" ? (
                                <div className="space-y-1">
                                  <Label htmlFor="assign-branch-uuid" className="text-xs text-text-2">
                                    Branch ID
                                  </Label>
                                  <Input
                                    id="assign-branch-uuid"
                                    value={scopeBranchId}
                                    onChange={(e) => setScopeBranchId(e.target.value as UUID)}
                                    placeholder="UUID"
                                    disabled={!canAssignRole}
                                  />
                                </div>
                              ) : null}
                            </div>
                          )
                        ) : null}

                        {assignError ? (
                          <div className="text-sm text-destructive">{assignError}</div>
                        ) : null}
                      </div>

                      <SheetFooter>
                        <Button
                          type="button"
                          disabled={!canAssignRole || assignM.isPending}
                          onClick={() => assignM.mutate()}
                        >
                          {assignM.isPending ? "Assigning..." : "Assign"}
                        </Button>
                      </SheetFooter>
                    </SheetContent>
                  </Sheet>
                </div>
              }
              isLoading={rolesQ.isLoading}
              error={rolesQ.error}
              onRetry={rolesQ.refetch}
              isEmpty={!rolesQ.isLoading && !rolesQ.error && assignments.length === 0}
              emptyState={
                <EmptyState
                  title="No role assignments"
                  description="Assign roles to grant access. Scopes restrict where permissions apply."
                  primaryAction={
                    canAssignRole ? (
                      <Button type="button" onClick={() => setAssignOpen(true)}>
                        Add role
                      </Button>
                    ) : null
                  }
                />
              }
              skeleton={{ rows: 6, cols: 5 }}
            >
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Role</TableHead>
                    <TableHead>Scope</TableHead>
                    <TableHead>Company</TableHead>
                    <TableHead>Branch</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {assignments.map((r) => (
                    <TableRow key={`${r.role_code}:${r.company_id ?? ""}:${r.branch_id ?? ""}`}>
                      <TableCell className="font-medium">{r.role_code}</TableCell>
                      <TableCell className="text-text-2">{scopeLabel(r)}</TableCell>
                      <TableCell className="font-mono text-xs text-text-3">
                        {r.company_id ?? "—"}
                      </TableCell>
                      <TableCell className="font-mono text-xs text-text-3">
                        {r.branch_id ?? "—"}
                      </TableCell>
                      <TableCell className="text-text-2">{formatDateTime(r.created_at)}</TableCell>
                      <TableCell className="text-end">
                        {canAssignRole ? (
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            onClick={() => {
                              setRemoveTarget(r);
                              setRemoveOpen(true);
                            }}
                          >
                            Remove
                          </Button>
                        ) : null}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </DataTable>
            </TabsContent>

            <TabsContent value="access">
            <DSCard surface="card" className="p-[var(--ds-space-20)]">
              <div className="text-sm font-semibold tracking-tight text-text-1">
                Effective access (V0)
              </div>
              <div className="mt-2 text-sm text-text-2">
                This is a derived summary of assigned roles in this tenant. Backend remains the source of truth for authorization.
              </div>

              <div className="mt-4 space-y-2">
                {assignments.length === 0 ? (
                  <EmptyState
                    title="No roles"
                    description="Assign roles to grant access."
                  />
                ) : (
                  <div className="space-y-2">
                    {assignments.map((r) => (
                      <div
                        key={`${r.role_code}:${r.company_id ?? ""}:${r.branch_id ?? ""}:summary`}
                        className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-3"
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          <div className="text-sm font-medium text-text-1">{r.role_code}</div>
                          <div className="text-xs text-text-3">{scopeLabel(r)}</div>
                        </div>
                        <div className="mt-1 text-xs text-text-3 font-mono">
                          tenant={r.tenant_id} company={r.company_id ?? "—"} branch={r.branch_id ?? "—"}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </DSCard>
            </TabsContent>
          </Tabs>
        }
        right={
          <RightPanelStack>
            <DSCard surface="panel" className="p-[var(--ds-space-20)]">
              <div className="text-sm font-semibold tracking-tight text-text-1">
                Quick actions
              </div>
              <div className="mt-2 space-y-2">
                <Button asChild variant="secondary" className="w-full justify-start">
                  <Link href="/settings/access/roles">Browse roles</Link>
                </Button>
                <Button asChild variant="secondary" className="w-full justify-start">
                  <Link href="/settings/access/permissions">Browse permissions</Link>
                </Button>
              </div>
            </DSCard>
          </RightPanelStack>
        }
      />

      {/* Confirm dialog (rendered at root for focus management). */}
      <Dialog open={removeOpen} onOpenChange={setRemoveOpen}>
        <DialogContent className="border-border-subtle bg-surface-2 backdrop-blur-xl">
          <DialogHeader>
            <DialogTitle>Remove role assignment</DialogTitle>
            <DialogDescription>
              This will remove the role assignment for this user. This action is audited.
            </DialogDescription>
          </DialogHeader>

          {removeTarget ? (
            <div className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-3 text-sm">
              <div>
                <span className="text-text-2">role</span>: {removeTarget.role_code}
              </div>
              <div className="font-mono text-xs text-text-3">
                company={removeTarget.company_id ?? "—"} branch={removeTarget.branch_id ?? "—"}
              </div>
            </div>
          ) : null}

          <DialogFooter className="gap-2 sm:gap-2">
            <Button type="button" variant="outline" onClick={() => setRemoveOpen(false)}>
              Cancel
            </Button>
            <Button
              type="button"
              variant="default"
              disabled={!removeTarget || removeM.isPending}
              onClick={() => removeM.mutate()}
            >
              {removeM.isPending ? "Removing..." : "Remove"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
