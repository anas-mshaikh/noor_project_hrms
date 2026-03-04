"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/lib/auth";
import { parseUuidParam } from "@/lib/guards";
import { useSelection } from "@/lib/selection";
import { cn } from "@/lib/utils";
import { toastApiError } from "@/lib/toastApiError";
import type {
  BranchOut,
  EmployeeDirectoryRowOut,
  HrEmployeeCreateIn,
  OrgUnitOut,
  UUID,
} from "@/lib/types";
import { listBranches, listOrgUnits } from "@/features/tenancy/api/tenancy";
import { tenancyKeys } from "@/features/tenancy/queryKeys";
import { createEmployee, listEmployees } from "@/features/hr-core/api/hrCore";
import { hrCoreKeys } from "@/features/hr-core/queryKeys";

import { DataTable } from "@/components/ds/DataTable";
import { DSCard } from "@/components/ds/DSCard";
import { EmptyState } from "@/components/ds/EmptyState";
import { FilterBar } from "@/components/ds/FilterBar";
import { PageHeader } from "@/components/ds/PageHeader";
import { RightPanelStack } from "@/components/ds/RightPanelStack";
import { StatusChip } from "@/components/ds/StatusChip";
import { ListRightPanelTemplate } from "@/components/ds/templates/ListRightPanelTemplate";
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
  // Avoid showing full UUIDs in tables unless needed.
  return id.length > 10 ? `${id.slice(0, 8)}…` : id;
}

function todayYmd(): string {
  const d = new Date();
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

export default function HrEmployeesPage() {
  const router = useRouter();
  const qc = useQueryClient();

  const permissions = useAuth((s) => s.permissions);
  const permSet = React.useMemo(() => new Set(permissions ?? []), [permissions]);
  const canWrite = permSet.has("hr:employee:write");
  const canReadTenancy = permSet.has("tenancy:read") || permSet.has("tenancy:write");

  const companyId = useSelection((s) => s.companyId);
  const branchId = useSelection((s) => s.branchId);

  const [q, setQ] = React.useState("");
  const [status, setStatus] = React.useState<string>("");
  const [filterBranchId, setFilterBranchId] = React.useState<UUID | "">("");
  const [filterOrgUnitId, setFilterOrgUnitId] = React.useState<UUID | "">("");
  const [limit, setLimit] = React.useState(25);
  const [offset, setOffset] = React.useState(0);

  React.useEffect(() => {
    setOffset(0);
  }, [q, status, filterBranchId, filterOrgUnitId, limit]);

  const branchesQ = useQuery({
    queryKey: tenancyKeys.branches(companyId ?? null),
    enabled: Boolean(companyId && canReadTenancy),
    queryFn: () => listBranches({ companyId: companyId as UUID }),
  });
  const branches = (branchesQ.data ?? []) as BranchOut[];

  const orgUnitsQ = useQuery({
    queryKey: companyId
      ? tenancyKeys.orgUnits({ companyId: companyId as UUID, branchId: filterBranchId || null })
      : ["tenancy", "org-units", "missing-company"],
    enabled: Boolean(companyId && canReadTenancy),
    queryFn: () =>
      listOrgUnits({
        companyId: companyId as UUID,
        branchId: filterBranchId || null,
      }),
  });
  const orgUnits = (orgUnitsQ.data ?? []) as OrgUnitOut[];

  const branchNameById = React.useMemo(() => {
    const m = new Map<string, string>();
    for (const b of branches) m.set(b.id, b.name);
    return m;
  }, [branches]);
  const orgUnitNameById = React.useMemo(() => {
    const m = new Map<string, string>();
    for (const u of orgUnits) m.set(u.id, u.name);
    return m;
  }, [orgUnits]);

  const employeesQ = useQuery({
    queryKey: hrCoreKeys.employees({
      companyId: companyId ? (companyId as UUID) : null,
      q: q.trim() ? q.trim() : null,
      status: status || null,
      branchId: filterBranchId || null,
      orgUnitId: filterOrgUnitId || null,
      limit,
      offset,
    }),
    enabled: Boolean(companyId),
    queryFn: () =>
      listEmployees({
        q: q.trim() ? q.trim() : null,
        status: status || null,
        branchId: filterBranchId || null,
        orgUnitId: filterOrgUnitId || null,
        limit,
        offset,
      }),
  });

  const items = (employeesQ.data?.items ?? []) as EmployeeDirectoryRowOut[];
  const paging = employeesQ.data?.paging ?? { limit, offset, total: 0 };
  const total = paging.total ?? 0;
  const canPrev = offset > 0;
  const canNext = offset + limit < total;

  const selectClassName = cn(
    "h-10 rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm",
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
    "disabled:cursor-not-allowed disabled:opacity-50"
  );

  // ----------------------------
  // Create employee (Sheet)
  // ----------------------------
  const [createOpen, setCreateOpen] = React.useState(false);
  const [employeeCode, setEmployeeCode] = React.useState("");
  const [firstName, setFirstName] = React.useState("");
  const [lastName, setLastName] = React.useState("");
  const [email, setEmail] = React.useState("");
  const [phone, setPhone] = React.useState("");
  const [startDate, setStartDate] = React.useState(() => todayYmd());
  const [createBranchId, setCreateBranchId] = React.useState<UUID | "">("");
  const [createOrgUnitId, setCreateOrgUnitId] = React.useState<UUID | "">("");

  React.useEffect(() => {
    // Prefer the active scope branch as the default employment branch.
    if (!createOpen) return;
    if (createBranchId) return;
    const id = parseUuidParam(branchId);
    if (id) setCreateBranchId(id);
  }, [branchId, createBranchId, createOpen]);

  const createM = useMutation({
    mutationFn: async () => {
      if (!companyId) throw new Error("Select a company first.");
      const cid = parseUuidParam(companyId);
      if (!cid) throw new Error("Invalid company id in selection.");

      const bid = parseUuidParam(createBranchId);
      if (!bid) throw new Error("Branch is required.");

      const payload: HrEmployeeCreateIn = {
        person: {
          first_name: firstName.trim(),
          last_name: lastName.trim(),
          email: email.trim() ? email.trim() : null,
          phone: phone.trim() ? phone.trim() : null,
          address: {},
        },
        employee: {
          company_id: cid,
          employee_code: employeeCode.trim(),
          join_date: startDate.trim() ? startDate.trim() : null,
          status: "ACTIVE",
        },
        employment: {
          start_date: startDate.trim(),
          branch_id: bid,
          org_unit_id: parseUuidParam(createOrgUnitId),
          is_primary: true,
        },
      };

      if (!payload.employee.employee_code) throw new Error("Employee code is required.");
      if (!payload.person.first_name) throw new Error("First name is required.");
      if (!payload.person.last_name) throw new Error("Last name is required.");
      if (!payload.employment.start_date) throw new Error("Start date is required.");

      return createEmployee(payload);
    },
    onSuccess: async (res) => {
      setCreateOpen(false);
      setEmployeeCode("");
      setFirstName("");
      setLastName("");
      setEmail("");
      setPhone("");
      setStartDate(todayYmd());
      setCreateBranchId("");
      setCreateOrgUnitId("");
      await qc.invalidateQueries({ queryKey: ["hr-core", "employees"] });
      toast.success("Employee created");
      router.push(`/hr/employees/${res.employee.id}`);
    },
    onError: (err) => toastApiError(err),
  });

  if (!companyId) {
    return (
      <EmptyState
        title="Select a company"
        description="Employee directory is company-scoped. Select a company from the scope picker to continue."
        primaryAction={
          <Button asChild variant="secondary">
            <Link href="/scope">Go to scope</Link>
          </Button>
        }
      />
    );
  }

  return (
    <ListRightPanelTemplate
      header={
        <PageHeader
          title="Employees"
          subtitle="Employee directory for the active company."
          actions={
            <Sheet open={createOpen} onOpenChange={setCreateOpen}>
              <SheetTrigger asChild>
                <Button type="button" disabled={!canWrite}>
                  Add employee
                </Button>
              </SheetTrigger>
              <SheetContent className="border-border-subtle bg-surface-2 backdrop-blur-xl">
                <SheetHeader>
                  <SheetTitle>Add employee</SheetTitle>
                  <SheetDescription>
                    Creates an employee profile and an initial employment record.
                  </SheetDescription>
                </SheetHeader>

                <div className="space-y-4 px-4">
                  <div className="space-y-1">
                    <Label htmlFor="emp-code" className="text-xs text-text-2">
                      Employee code
                    </Label>
                    <Input
                      id="emp-code"
                      value={employeeCode}
                      onChange={(e) => setEmployeeCode(e.target.value)}
                      placeholder="E0001"
                    />
                  </div>

                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="space-y-1">
                      <Label htmlFor="emp-first" className="text-xs text-text-2">
                        First name
                      </Label>
                      <Input
                        id="emp-first"
                        value={firstName}
                        onChange={(e) => setFirstName(e.target.value)}
                      />
                    </div>
                    <div className="space-y-1">
                      <Label htmlFor="emp-last" className="text-xs text-text-2">
                        Last name
                      </Label>
                      <Input
                        id="emp-last"
                        value={lastName}
                        onChange={(e) => setLastName(e.target.value)}
                      />
                    </div>
                  </div>

                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="space-y-1">
                      <Label htmlFor="emp-email" className="text-xs text-text-2">
                        Email (optional)
                      </Label>
                      <Input
                        id="emp-email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="employee@company.com"
                      />
                    </div>
                    <div className="space-y-1">
                      <Label htmlFor="emp-phone" className="text-xs text-text-2">
                        Phone (optional)
                      </Label>
                      <Input
                        id="emp-phone"
                        value={phone}
                        onChange={(e) => setPhone(e.target.value)}
                        placeholder="+966..."
                      />
                    </div>
                  </div>

                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="space-y-1">
                      <Label htmlFor="emp-start" className="text-xs text-text-2">
                        Start date
                      </Label>
                      <Input
                        id="emp-start"
                        type="date"
                        value={startDate}
                        onChange={(e) => setStartDate(e.target.value)}
                      />
                    </div>
                    <div className="space-y-1">
                      <Label htmlFor="emp-branch" className="text-xs text-text-2">
                        Branch
                      </Label>
                      {canReadTenancy ? (
                        <select
                          id="emp-branch"
                          className={selectClassName}
                          value={createBranchId}
                          onChange={(e) => setCreateBranchId(e.target.value as UUID)}
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
                          id="emp-branch"
                          value={createBranchId}
                          onChange={(e) => setCreateBranchId(e.target.value as UUID)}
                          placeholder="branch uuid"
                        />
                      )}
                    </div>
                  </div>

                  <div className="space-y-1">
                    <Label htmlFor="emp-orgunit" className="text-xs text-text-2">
                      Org unit (optional)
                    </Label>
                    {canReadTenancy ? (
                      <select
                        id="emp-orgunit"
                        className={selectClassName}
                        value={createOrgUnitId}
                        onChange={(e) => setCreateOrgUnitId(e.target.value as UUID)}
                      >
                        <option value="">None</option>
                        {orgUnits.map((u) => (
                          <option key={u.id} value={u.id}>
                            {u.name}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <Input
                        id="emp-orgunit"
                        value={createOrgUnitId}
                        onChange={(e) => setCreateOrgUnitId(e.target.value as UUID)}
                        placeholder="org unit uuid"
                      />
                    )}
                  </div>
                </div>

                <SheetFooter>
                  <Button
                    type="button"
                    disabled={!canWrite || createM.isPending}
                    onClick={() => createM.mutate()}
                  >
                    {createM.isPending ? "Creating..." : "Create"}
                  </Button>
                </SheetFooter>
              </SheetContent>
            </Sheet>
          }
        />
      }
      main={
        <DataTable
          toolbar={
            <FilterBar
              search={{
                value: q,
                onChange: setQ,
                placeholder: "Search employees…",
              }}
              chips={
                <div className="flex flex-wrap items-center gap-3">
                  <div className="flex items-center gap-2">
                    <div className="text-xs text-text-2">Status</div>
                    <select
                      className={cn(selectClassName, "h-9 py-1")}
                      value={status}
                      onChange={(e) => setStatus(e.target.value)}
                    >
                      <option value="">All</option>
                      <option value="ACTIVE">ACTIVE</option>
                      <option value="INACTIVE">INACTIVE</option>
                      <option value="TERMINATED">TERMINATED</option>
                    </select>
                  </div>

                  {canReadTenancy ? (
                    <div className="flex items-center gap-2">
                      <div className="text-xs text-text-2">Branch</div>
                      <select
                        className={cn(selectClassName, "h-9 py-1")}
                        value={filterBranchId}
                        onChange={(e) => setFilterBranchId(e.target.value as UUID)}
                      >
                        <option value="">All</option>
                        {branches.map((b) => (
                          <option key={b.id} value={b.id}>
                            {b.name}
                          </option>
                        ))}
                      </select>
                    </div>
                  ) : null}

                  {canReadTenancy ? (
                    <div className="flex items-center gap-2">
                      <div className="text-xs text-text-2">Org unit</div>
                      <select
                        className={cn(selectClassName, "h-9 py-1")}
                        value={filterOrgUnitId}
                        onChange={(e) => setFilterOrgUnitId(e.target.value as UUID)}
                      >
                        <option value="">All</option>
                        {orgUnits.map((u) => (
                          <option key={u.id} value={u.id}>
                            {u.name}
                          </option>
                        ))}
                      </select>
                    </div>
                  ) : null}
                </div>
              }
              rightActions={
                <div className="flex flex-wrap items-center gap-2">
                  <div className="text-xs text-text-2">
                    {total ? (
                      <>
                        {offset + 1}-{Math.min(offset + limit, total)} of {total}
                      </>
                    ) : (
                      "0 results"
                    )}
                  </div>
                  <select
                    className={cn(selectClassName, "h-9 py-1")}
                    value={limit}
                    onChange={(e) => setLimit(Number(e.target.value))}
                  >
                    <option value={25}>25</option>
                    <option value={50}>50</option>
                    <option value={100}>100</option>
                  </select>
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={!canPrev}
                    onClick={() => setOffset(Math.max(0, offset - limit))}
                  >
                    Prev
                  </Button>
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={!canNext}
                    onClick={() => setOffset(offset + limit)}
                  >
                    Next
                  </Button>
                </div>
              }
              onClearAll={() => {
                setQ("");
                setStatus("");
                setFilterBranchId("");
                setFilterOrgUnitId("");
              }}
              clearDisabled={!q && !status && !filterBranchId && !filterOrgUnitId}
            />
          }
          isLoading={employeesQ.isLoading}
          error={employeesQ.error}
          onRetry={employeesQ.refetch}
          isEmpty={!employeesQ.isLoading && !employeesQ.error && items.length === 0}
          emptyState={
            <EmptyState
              title="No employees"
              description="Create your first employee profile to start managing HR records."
              primaryAction={
                canWrite ? (
                  <Button type="button" onClick={() => setCreateOpen(true)}>
                    Add employee
                  </Button>
                ) : null
              }
            />
          }
          skeleton={{ rows: 7, cols: 6 }}
        >
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Code</TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Branch</TableHead>
                <TableHead>Org unit</TableHead>
                <TableHead>ESS</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((e) => (
                <TableRow key={e.employee_id} className="cursor-pointer">
                  <TableCell className="font-medium">
                    <Link
                      href={`/hr/employees/${e.employee_id}`}
                      className="hover:underline"
                    >
                      {e.employee_code}
                    </Link>
                  </TableCell>
                  <TableCell className="text-text-1">{e.full_name}</TableCell>
                  <TableCell>
                    <StatusChip status={e.status} />
                  </TableCell>
                  <TableCell className="text-text-2">
                    {e.branch_id
                      ? branchNameById.get(e.branch_id) ?? formatId(e.branch_id)
                      : "—"}
                  </TableCell>
                  <TableCell className="text-text-2">
                    {e.org_unit_id
                      ? orgUnitNameById.get(e.org_unit_id) ?? formatId(e.org_unit_id)
                      : "—"}
                  </TableCell>
                  <TableCell className="text-text-2">
                    {e.has_user_link ? "Enabled" : "Not linked"}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </DataTable>
      }
      right={
        <RightPanelStack>
          <DSCard surface="panel" className="p-[var(--ds-space-20)]">
            <div className="text-sm font-semibold tracking-tight text-text-1">
              Scope
            </div>
            <div className="mt-2 space-y-2 text-sm text-text-2">
              <div>
                <span className="text-text-3">company</span>:{" "}
                <span className="text-text-1">{formatId(companyId)}</span>
              </div>
              <div>
                <span className="text-text-3">branch</span>:{" "}
                <span className="text-text-1">
                  {branchId ? formatId(branchId) : "not selected"}
                </span>
              </div>
            </div>
          </DSCard>

          <DSCard surface="panel" className="p-[var(--ds-space-20)]">
            <div className="text-sm font-semibold tracking-tight text-text-1">
              Summary
            </div>
            <div className="mt-2 grid grid-cols-2 gap-3 text-sm">
              <div className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-3">
                <div className="text-xs text-text-2">employees</div>
                <div className="mt-1 text-lg font-semibold text-text-1">{total}</div>
              </div>
              <div className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-3">
                <div className="text-xs text-text-2">page size</div>
                <div className="mt-1 text-lg font-semibold text-text-1">{limit}</div>
              </div>
            </div>
          </DSCard>
        </RightPanelStack>
      }
    />
  );
}

