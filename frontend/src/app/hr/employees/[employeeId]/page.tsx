"use client";

import * as React from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { toast } from "sonner";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/lib/auth";
import { parseUuidParam } from "@/lib/guards";
import { useSelection } from "@/lib/selection";
import { cn } from "@/lib/utils";
import { toastApiError } from "@/lib/toastApiError";
import type {
  BranchOut,
  HrEmployee360Out,
  HrEmployeeLinkUserIn,
  HrEmploymentChangeIn,
  HrEmploymentOut,
  IamUserOut,
  OrgUnitOut,
  UUID,
} from "@/lib/types";
import { listBranches, listOrgUnits } from "@/features/tenancy/api/tenancy";
import { tenancyKeys } from "@/features/tenancy/queryKeys";
import { listUsers } from "@/features/iam/api/iam";
import { iamKeys } from "@/features/iam/queryKeys";
import {
  changeEmployment,
  getEmployee,
  linkEmployeeUser,
  listEmploymentHistory,
} from "@/features/hr-core/api/hrCore";
import { hrCoreKeys } from "@/features/hr-core/queryKeys";
import { employeeDocsHref } from "@/features/dms/routes";

import { DSCard } from "@/components/ds/DSCard";
import { EmptyState } from "@/components/ds/EmptyState";
import { ErrorState } from "@/components/ds/ErrorState";
import { PageHeader } from "@/components/ds/PageHeader";
import { RightPanelStack } from "@/components/ds/RightPanelStack";
import { StatusChip } from "@/components/ds/StatusChip";
import { EntityProfileTemplate } from "@/components/ds/templates/EntityProfileTemplate";
import { Button } from "@/components/ui/button";
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

function formatId(id: string | null | undefined): string {
  if (!id) return "—";
  return id.length > 10 ? `${id.slice(0, 8)}…` : id;
}

function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  return value;
}

function todayYmd(): string {
  const d = new Date();
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

export default function HrEmployeeDetailPage({ params }: { params: { employeeId?: string } }) {
  const router = useRouter();
  const routeParams = useParams() as { employeeId?: string | string[] };
  const employeeIdRaw =
    (Array.isArray(routeParams.employeeId) ? routeParams.employeeId[0] : routeParams.employeeId) ??
    params?.employeeId ??
    null;
  const employeeId = parseUuidParam(employeeIdRaw);

  const companyId = useSelection((s) => s.companyId);
  const branchId = useSelection((s) => s.branchId);
  const companyUuid = parseUuidParam(companyId);

  const permissions = useAuth((s) => s.permissions);
  const permSet = React.useMemo(() => new Set(permissions ?? []), [permissions]);
  const canWrite = permSet.has("hr:employee:write");
  const canReadTenancy = permSet.has("tenancy:read") || permSet.has("tenancy:write");
  const canReadIamUsers = permSet.has("iam:user:read") || permSet.has("iam:user:write");

  const qc = useQueryClient();

  const selectClassName = cn(
    "h-10 rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm",
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
    "disabled:cursor-not-allowed disabled:opacity-50"
  );

  const employeeQ = useQuery({
    queryKey: hrCoreKeys.employee({ companyId: companyUuid, employeeId }),
    enabled: Boolean(companyUuid && employeeId),
    queryFn: () => getEmployee({ employeeId: employeeId as UUID, companyId: companyUuid }),
  });

  const employee = employeeQ.data as HrEmployee360Out | undefined;

  const [tab, setTab] = React.useState("overview");
  function handleTabChange(nextTab: string) {
    if (nextTab === "documents") {
      if (employeeId) router.push(employeeDocsHref({ employeeId }));
      return;
    }
    setTab(nextTab);
  }

  // ------------------------------------------------------------
  // Employment tab: history + change
  // ------------------------------------------------------------
  const branchesQ = useQuery({
    queryKey: tenancyKeys.branches(companyUuid),
    enabled: Boolean(companyUuid && canReadTenancy),
    queryFn: () => listBranches({ companyId: companyUuid }),
  });
  const branches = (branchesQ.data ?? []) as BranchOut[];

  const employmentQ = useQuery({
    queryKey: hrCoreKeys.employmentHistory({ companyId: companyUuid, employeeId }),
    enabled: Boolean(companyUuid && employeeId && tab === "employment"),
    queryFn: () => listEmploymentHistory({ employeeId: employeeId as UUID, companyId: companyUuid }),
  });
  const employment = (employmentQ.data ?? []) as HrEmploymentOut[];

  const [changeOpen, setChangeOpen] = React.useState(false);
  const [changeStartDate, setChangeStartDate] = React.useState(() => todayYmd());
  const [changeBranchId, setChangeBranchId] = React.useState<UUID | "">("");
  const [changeOrgUnitId, setChangeOrgUnitId] = React.useState<UUID | "">("");

  React.useEffect(() => {
    if (!changeOpen) return;
    if (changeBranchId) return;
    const id = parseUuidParam(branchId);
    if (id) setChangeBranchId(id);
  }, [branchId, changeBranchId, changeOpen]);

  const changeOrgUnitsQ = useQuery({
    queryKey: companyUuid
      ? tenancyKeys.orgUnits({ companyId: companyUuid, branchId: changeBranchId || null })
      : (["tenancy", "org-units", null, changeBranchId || null] as const),
    enabled: Boolean(companyUuid && canReadTenancy && changeOpen),
    queryFn: () =>
      listOrgUnits({
        companyId: companyUuid as UUID,
        branchId: changeBranchId || null,
      }),
  });
  const changeOrgUnits = (changeOrgUnitsQ.data ?? []) as OrgUnitOut[];

  const changeM = useMutation({
    mutationFn: async () => {
      if (!employeeId || !companyUuid) throw new Error("Employee context is required.");
      const bid = parseUuidParam(changeBranchId);
      if (!bid) throw new Error("Branch is required.");
      if (!changeStartDate.trim()) throw new Error("Start date is required.");

      const payload: HrEmploymentChangeIn = {
        start_date: changeStartDate.trim(),
        branch_id: bid,
        org_unit_id: parseUuidParam(changeOrgUnitId),
      };
      return changeEmployment({
        employeeId,
        companyId: companyUuid,
        payload,
      });
    },
    onSuccess: async () => {
      setChangeOpen(false);
      setChangeStartDate(todayYmd());
      setChangeBranchId("");
      setChangeOrgUnitId("");
      await qc.invalidateQueries({ queryKey: ["hr-core", "employee"] });
      await qc.invalidateQueries({ queryKey: ["hr-core", "employment-history"] });
      toast.success("Employment updated");
    },
    onError: (err) => toastApiError(err),
  });

  // ------------------------------------------------------------
  // Link user tab
  // ------------------------------------------------------------
  const linkedUser = employee?.linked_user ?? null;

  const [userSearch, setUserSearch] = React.useState("");
  const [selectedUserId, setSelectedUserId] = React.useState<UUID | "">("");

  const userSearchQ = useQuery({
    queryKey: iamKeys.users({
      q: userSearch.trim() ? userSearch.trim() : null,
      status: null,
      limit: 10,
      offset: 0,
    }),
    enabled: tab === "link-user" && canReadIamUsers && Boolean(userSearch.trim()),
    queryFn: () =>
      listUsers({
        q: userSearch.trim() ? userSearch.trim() : null,
        status: null,
        limit: 10,
        offset: 0,
      }),
  });
  const userResults = (userSearchQ.data?.items ?? []) as IamUserOut[];

  const linkM = useMutation({
    mutationFn: async () => {
      if (!employeeId || !companyUuid) throw new Error("Employee context is required.");
      if (linkedUser) throw new Error("Employee is already linked.");
      const uid = parseUuidParam(selectedUserId);
      if (!uid) throw new Error("User id is required.");
      const payload: HrEmployeeLinkUserIn = { user_id: uid };
      return linkEmployeeUser({
        employeeId,
        companyId: companyUuid,
        payload,
      });
    },
    onSuccess: async () => {
      setSelectedUserId("");
      setUserSearch("");
      await qc.invalidateQueries({ queryKey: ["hr-core", "employee"] });
      toast.success("User linked");
    },
    onError: (err) => toastApiError(err),
  });

  // ------------------------------------------------------------
  // Render
  // ------------------------------------------------------------
  if (!companyUuid) {
    return (
      <EmptyState
        title="Select a company"
        description="Employee profiles are company-scoped. Select a company from the scope picker to continue."
        primaryAction={
          <Button asChild variant="secondary">
            <Link href="/scope">Go to scope</Link>
          </Button>
        }
      />
    );
  }

  if (!employeeIdRaw) {
    return (
      <ErrorState
        title="Missing employee id"
        error={new Error("Open an employee from the directory.")}
        details={
          <Button asChild variant="outline">
            <Link href="/hr/employees">Back to employees</Link>
          </Button>
        }
      />
    );
  }

  if (!employeeId) {
    return (
      <ErrorState
        title="Invalid employee id"
        error={new Error(`Got: ${String(employeeIdRaw)}`)}
        details={
          <Button asChild variant="outline">
            <Link href="/hr/employees">Back to employees</Link>
          </Button>
        }
      />
    );
  }

  return (
    <EntityProfileTemplate
      header={
        <PageHeader
          title={employee ? employee.employee.employee_code : "Employee"}
          subtitle={
            employee
              ? `${employee.person.first_name} ${employee.person.last_name}`.trim()
              : "Employee profile"
          }
          actions={
            <Button asChild type="button" variant="secondary">
              <Link href="/hr/employees">Back</Link>
            </Button>
          }
          meta={
            employee ? (
              <div className="flex flex-wrap items-center gap-2">
                <StatusChip status={employee.employee.status} />
                {employee.current_employment?.branch_id ? (
                  <div className="rounded-full border border-border-subtle bg-surface-1 px-3 py-1 text-xs text-text-2">
                    branch {formatId(employee.current_employment.branch_id)}
                  </div>
                ) : null}
              </div>
            ) : null
          }
        />
      }
      tabs={
        <Tabs value={tab} onValueChange={handleTabChange}>
          <TabsList>
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="employment">Employment</TabsTrigger>
            <TabsTrigger value="link-user">Link user</TabsTrigger>
            <TabsTrigger value="documents">
              Documents
            </TabsTrigger>
            <TabsTrigger value="payroll">
              Payroll
            </TabsTrigger>
          </TabsList>
        </Tabs>
      }
      main={
        <>
          {employeeQ.isLoading ? (
            <DSCard surface="card" className="p-[var(--ds-space-20)]">
              <div className="text-sm text-text-2">Loading…</div>
            </DSCard>
          ) : employeeQ.error ? (
            <ErrorState
              title="Could not load employee"
              error={employeeQ.error}
              onRetry={employeeQ.refetch}
            />
          ) : !employee ? (
            <EmptyState title="Employee not found" description="This employee does not exist or you do not have access." />
          ) : (
            <Tabs value={tab} onValueChange={handleTabChange}>
              <TabsContent value="overview" className="mt-0">
                <div className="space-y-6">
                  <DSCard surface="card" className="p-[var(--ds-space-20)]">
                    <div className="text-sm font-semibold tracking-tight text-text-1">
                      Overview
                    </div>
                    <div className="mt-4 grid gap-4 md:grid-cols-2">
                      <div className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-4">
                        <div className="text-xs text-text-2">Employee code</div>
                        <div className="mt-1 text-sm font-medium text-text-1">
                          {employee.employee.employee_code}
                        </div>
                      </div>
                      <div className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-4">
                        <div className="text-xs text-text-2">Status</div>
                        <div className="mt-1">
                          <StatusChip status={employee.employee.status} />
                        </div>
                      </div>
                      <div className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-4">
                        <div className="text-xs text-text-2">Join date</div>
                        <div className="mt-1 text-sm text-text-1">
                          {formatDate(employee.employee.join_date)}
                        </div>
                      </div>
                      <div className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-4">
                        <div className="text-xs text-text-2">Termination date</div>
                        <div className="mt-1 text-sm text-text-1">
                          {formatDate(employee.employee.termination_date)}
                        </div>
                      </div>
                    </div>
                  </DSCard>

                  <DSCard surface="card" className="p-[var(--ds-space-20)]">
                    <div className="text-sm font-semibold tracking-tight text-text-1">
                      Contact
                    </div>
                    <div className="mt-4 grid gap-4 md:grid-cols-2">
                      <div className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-4">
                        <div className="text-xs text-text-2">Email</div>
                        <div className="mt-1 text-sm text-text-1">
                          {employee.person.email ?? "—"}
                        </div>
                      </div>
                      <div className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-4">
                        <div className="text-xs text-text-2">Phone</div>
                        <div className="mt-1 text-sm text-text-1">
                          {employee.person.phone ?? "—"}
                        </div>
                      </div>
                    </div>
                  </DSCard>
                </div>
              </TabsContent>

              <TabsContent value="employment" className="mt-0">
                <DSCard surface="card" className="p-[var(--ds-space-20)]">
                  <div className="flex flex-wrap items-center gap-3">
                    <div className="text-sm font-semibold tracking-tight text-text-1">
                      Employment history
                    </div>
                    <div className="ms-auto">
                      <Sheet open={changeOpen} onOpenChange={setChangeOpen}>
                        <SheetTrigger asChild>
                          <Button type="button" disabled={!canWrite}>
                            Add record
                          </Button>
                        </SheetTrigger>
                        <SheetContent className="border-border-subtle bg-surface-2 backdrop-blur-xl">
                          <SheetHeader>
                            <SheetTitle>Add employment record</SheetTitle>
                            <SheetDescription>
                              Adds a new employment record starting on the selected date.
                            </SheetDescription>
                          </SheetHeader>

                          <div className="space-y-4 px-4">
                            <div className="space-y-1">
                              <Label htmlFor="emp-change-start" className="text-xs text-text-2">
                                Start date
                              </Label>
                              <Input
                                id="emp-change-start"
                                type="date"
                                value={changeStartDate}
                                onChange={(e) => setChangeStartDate(e.target.value)}
                              />
                            </div>
                            <div className="space-y-1">
                              <Label htmlFor="emp-change-branch" className="text-xs text-text-2">
                                Branch
                              </Label>
                              {canReadTenancy ? (
                                <select
                                  id="emp-change-branch"
                                  className={selectClassName}
                                  value={changeBranchId}
                                  onChange={(e) => setChangeBranchId(e.target.value as UUID)}
                                >
                                  <option value="">Select branch…</option>
                                  {branches.map((b) => (
                                    <option key={b.id} value={b.id}>
                                      {b.name} ({b.code})
                                    </option>
                                  ))}
                                </select>
                              ) : (
                                <Input
                                  id="emp-change-branch"
                                  value={changeBranchId}
                                  onChange={(e) => setChangeBranchId(e.target.value as UUID)}
                                  placeholder="branch uuid"
                                />
                              )}
                            </div>
                            <div className="space-y-1">
                              <Label htmlFor="emp-change-orgunit" className="text-xs text-text-2">
                                Org unit (optional)
                              </Label>
                              {canReadTenancy ? (
                                <select
                                  id="emp-change-orgunit"
                                  className={selectClassName}
                                  value={changeOrgUnitId}
                                  onChange={(e) => setChangeOrgUnitId(e.target.value as UUID)}
                                >
                                  <option value="">None</option>
                                  {changeOrgUnits.map((u) => (
                                    <option key={u.id} value={u.id}>
                                      {u.name}
                                    </option>
                                  ))}
                                </select>
                              ) : (
                                <Input
                                  id="emp-change-orgunit"
                                  value={changeOrgUnitId}
                                  onChange={(e) => setChangeOrgUnitId(e.target.value as UUID)}
                                  placeholder="org unit uuid"
                                />
                              )}
                            </div>
                          </div>

                          <SheetFooter>
                            <Button
                              type="button"
                              disabled={!canWrite || changeM.isPending}
                              onClick={() => changeM.mutate()}
                            >
                              {changeM.isPending ? "Saving..." : "Save"}
                            </Button>
                          </SheetFooter>
                        </SheetContent>
                      </Sheet>
                    </div>
                  </div>

                  <div className="mt-4">
                    {employmentQ.isLoading ? (
                      <div className="text-sm text-text-2">Loading…</div>
                    ) : employmentQ.error ? (
                      <ErrorState
                        title="Could not load employment history"
                        error={employmentQ.error}
                        onRetry={employmentQ.refetch}
                        variant="inline"
                        className="max-w-none"
                      />
                    ) : employment.length === 0 ? (
                      <EmptyState
                        title="No employment records"
                        description="This employee does not have any employment history yet."
                      />
                    ) : (
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Start</TableHead>
                            <TableHead>End</TableHead>
                            <TableHead>Branch</TableHead>
                            <TableHead>Org unit</TableHead>
                            <TableHead>Primary</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {employment.map((r) => (
                            <TableRow key={r.id}>
                              <TableCell className="font-medium">{r.start_date}</TableCell>
                              <TableCell className="text-text-2">{r.end_date ?? "—"}</TableCell>
                              <TableCell className="text-text-2">
                                {formatId(r.branch_id)}
                              </TableCell>
                              <TableCell className="text-text-2">
                                {r.org_unit_id ? formatId(r.org_unit_id) : "—"}
                              </TableCell>
                              <TableCell className="text-text-2">
                                {r.is_primary ? "Yes" : "—"}
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    )}
                  </div>
                </DSCard>
              </TabsContent>

              <TabsContent value="link-user" className="mt-0">
                <DSCard surface="card" className="p-[var(--ds-space-20)]">
                  <div className="text-sm font-semibold tracking-tight text-text-1">
                    Link user account
                  </div>
                  <div className="mt-2 text-sm text-text-2">
                    Link an IAM user to enable ESS/MSS access for this employee.
                  </div>

                  {linkedUser ? (
                    <div className="mt-4 rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-4">
                      <div className="text-xs text-text-2">Linked user</div>
                      <div className="mt-1 text-sm font-medium text-text-1">
                        {linkedUser.email} ({linkedUser.status})
                      </div>
                      <div className="mt-1 text-xs text-text-2">
                        linked at {linkedUser.linked_at}
                      </div>
                    </div>
                  ) : (
                    <div className="mt-4 space-y-4">
                      {canReadIamUsers ? (
                        <div className="space-y-2">
                          <Label htmlFor="user-search" className="text-xs text-text-2">
                            Search users
                          </Label>
                          <Input
                            id="user-search"
                            value={userSearch}
                            onChange={(e) => setUserSearch(e.target.value)}
                            placeholder="Search by email…"
                          />
                          {userSearchQ.isLoading ? (
                            <div className="text-sm text-text-2">Searching…</div>
                          ) : userResults.length ? (
                            <div className="space-y-2">
                              {userResults.map((u) => (
                                <button
                                  key={u.id}
                                  type="button"
                                  onClick={() => setSelectedUserId(u.id)}
                                  className={cn(
                                    "flex w-full items-center justify-between rounded-[var(--ds-radius-16)] border px-4 py-3 text-left text-sm",
                                    selectedUserId === u.id
                                      ? "border-border-strong bg-surface-2"
                                      : "border-border-subtle bg-surface-1 hover:bg-surface-2"
                                  )}
                                >
                                  <div className="min-w-0">
                                    <div className="truncate font-medium text-text-1">{u.email}</div>
                                    <div className="mt-0.5 text-xs text-text-2">{u.status}</div>
                                  </div>
                                  <div className="text-xs text-text-3">{formatId(u.id)}</div>
                                </button>
                              ))}
                            </div>
                          ) : userSearch.trim() ? (
                            <div className="text-sm text-text-2">No users found.</div>
                          ) : null}
                        </div>
                      ) : (
                        <div className="space-y-2">
                          <Label htmlFor="user-id" className="text-xs text-text-2">
                            User id
                          </Label>
                          <Input
                            id="user-id"
                            value={selectedUserId}
                            onChange={(e) => setSelectedUserId(e.target.value as UUID)}
                            placeholder="uuid"
                          />
                        </div>
                      )}

                      <div className="flex items-center gap-3">
                        <Button
                          type="button"
                          disabled={!canWrite || linkM.isPending || !selectedUserId}
                          onClick={() => linkM.mutate()}
                        >
                          {linkM.isPending ? "Linking..." : "Link user"}
                        </Button>
                        <div className="text-xs text-text-2">
                          Selected: {selectedUserId ? formatId(selectedUserId) : "—"}
                        </div>
                      </div>
                    </div>
                  )}
                </DSCard>
              </TabsContent>

              <TabsContent value="payroll" className="mt-0">
                <DSCard surface="card" className="p-[var(--ds-space-20)]">
                  <div className="space-y-4">
                    <div>
                      <div className="text-sm font-semibold tracking-tight text-text-1">
                        Payroll
                      </div>
                      <div className="mt-1 text-sm text-text-2">
                        Manage compensation records for this employee in the payroll workspace.
                      </div>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <Button asChild type="button">
                        <Link href={`/payroll/compensation?employeeId=${employeeId}`}>
                          Open compensation
                        </Link>
                      </Button>
                    </div>
                  </div>
                </DSCard>
              </TabsContent>
            </Tabs>
          )}
        </>
      }
      right={
        <RightPanelStack>
          <DSCard surface="panel" className="p-[var(--ds-space-20)]">
            <div className="text-sm font-semibold tracking-tight text-text-1">
              Current employment
            </div>
            <div className="mt-3 space-y-2 text-sm text-text-2">
              <div>
                <span className="text-text-3">branch</span>:{" "}
                <span className="text-text-1">
                  {employee?.current_employment?.branch_id
                    ? formatId(employee.current_employment.branch_id)
                    : "—"}
                </span>
              </div>
              <div>
                <span className="text-text-3">org unit</span>:{" "}
                <span className="text-text-1">
                  {employee?.current_employment?.org_unit_id
                    ? formatId(employee.current_employment.org_unit_id)
                    : "—"}
                </span>
              </div>
            </div>
          </DSCard>

          <DSCard surface="panel" className="p-[var(--ds-space-20)]">
            <div className="text-sm font-semibold tracking-tight text-text-1">
              Manager
            </div>
            <div className="mt-2 text-sm text-text-2">
              {employee?.manager ? employee.manager.display_name : "—"}
            </div>
          </DSCard>
        </RightPanelStack>
      }
    />
  );
}
