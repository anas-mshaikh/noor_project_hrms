"use client";

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/lib/auth";
import { useSelection } from "@/lib/selection";
import { cn } from "@/lib/utils";
import { toastApiError } from "@/lib/toastApiError";
import type { BranchCreate, BranchOut, CompanyOut, UUID } from "@/lib/types";
import { createBranch, listBranches, listCompanies } from "@/features/tenancy/api/tenancy";
import { tenancyKeys } from "@/features/tenancy/queryKeys";

import { DataTable } from "@/components/ds/DataTable";
import { DSCard } from "@/components/ds/DSCard";
import { EmptyState } from "@/components/ds/EmptyState";
import { FilterBar } from "@/components/ds/FilterBar";
import { PageHeader } from "@/components/ds/PageHeader";
import { RightPanelStack } from "@/components/ds/RightPanelStack";
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

function toCompanyOptions(companies: CompanyOut[]): Array<{ id: UUID; label: string }> {
  return companies.map((c) => ({ id: c.id, label: c.name }));
}

export default function BranchesPage() {
  const selectedCompanyId = useSelection((s) => s.companyId);
  const permissions = useAuth((s) => s.permissions);
  const canWrite = React.useMemo(
    () => new Set(permissions ?? []).has("tenancy:write"),
    [permissions]
  );

  const qc = useQueryClient();

  const companiesQ = useQuery({
    queryKey: tenancyKeys.companies(),
    queryFn: () => listCompanies(),
  });

  const companies = (companiesQ.data ?? []) as CompanyOut[];
  const companyOptions = React.useMemo(() => toCompanyOptions(companies), [companies]);
  const companyNameById = React.useMemo(() => {
    const m = new Map<string, string>();
    for (const c of companies) m.set(c.id, c.name);
    return m;
  }, [companies]);

  const [filterCompanyId, setFilterCompanyId] = React.useState<UUID | null>(
    selectedCompanyId ?? null
  );

  const branchesQ = useQuery({
    queryKey: tenancyKeys.branches(filterCompanyId),
    queryFn: () => listBranches({ companyId: filterCompanyId }),
  });

  const branches = (branchesQ.data ?? []) as BranchOut[];

  const [open, setOpen] = React.useState(false);
  const [companyId, setCompanyId] = React.useState<UUID | "">(
    (filterCompanyId ?? selectedCompanyId ?? "") as UUID | ""
  );
  const [name, setName] = React.useState("");
  const [code, setCode] = React.useState("");
  const [timezone, setTimezone] = React.useState("");

  // Keep create form company aligned when filter/selection changes.
  React.useEffect(() => {
    if (companyId) return;
    if (filterCompanyId) setCompanyId(filterCompanyId);
    else if (selectedCompanyId) setCompanyId(selectedCompanyId);
  }, [filterCompanyId, selectedCompanyId, companyId]);

  const createM = useMutation({
    mutationFn: async () => {
      if (!companyId) throw new Error("Company is required.");
      const payload: BranchCreate = {
        company_id: companyId,
        name: name.trim(),
        code: code.trim(),
        timezone: timezone.trim() ? timezone.trim() : null,
        address: {},
      };
      if (!payload.name) throw new Error("Branch name is required.");
      if (!payload.code) throw new Error("Branch code is required.");
      return createBranch(payload);
    },
    onSuccess: async () => {
      setOpen(false);
      setName("");
      setCode("");
      setTimezone("");
      await qc.invalidateQueries({ queryKey: tenancyKeys.branches(filterCompanyId) });
    },
    onError: (err) => toastApiError(err),
  });

  const selectClassName = cn(
    "h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm",
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
    "disabled:cursor-not-allowed disabled:opacity-50"
  );

  const noCompanies = !companiesQ.isLoading && !companiesQ.error && companies.length === 0;

  return (
    <ListRightPanelTemplate
      header={
        <PageHeader
          title="Branches"
          subtitle="Create and view branches under companies."
          actions={
            <Sheet open={open} onOpenChange={setOpen}>
              <SheetTrigger asChild>
                <Button type="button" disabled={!canWrite || noCompanies}>
                  Create branch
                </Button>
              </SheetTrigger>
              <SheetContent className="border-border-subtle bg-surface-2 backdrop-blur-xl">
                <SheetHeader>
                  <SheetTitle>Create branch</SheetTitle>
                  <SheetDescription>
                    Branches are scoped to a company. Choose a company first.
                  </SheetDescription>
                </SheetHeader>

                <div className="space-y-4 px-4">
                  <div className="space-y-1">
                    <Label htmlFor="branch-company" className="text-xs text-text-2">
                      Company
                    </Label>
                    <select
                      id="branch-company"
                      className={selectClassName}
                      value={companyId}
                      onChange={(e) => setCompanyId((e.target.value as UUID) || "")}
                      disabled={!canWrite || companiesQ.isLoading || noCompanies}
                    >
                      <option value="">Select company...</option>
                      {companyOptions.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="branch-name" className="text-xs text-text-2">
                      Name
                    </Label>
                    <Input
                      id="branch-name"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                    />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="branch-code" className="text-xs text-text-2">
                      Code
                    </Label>
                    <Input
                      id="branch-code"
                      value={code}
                      onChange={(e) => setCode(e.target.value)}
                      placeholder="e.g. RYD"
                    />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="branch-timezone" className="text-xs text-text-2">
                      Timezone (optional)
                    </Label>
                    <Input
                      id="branch-timezone"
                      value={timezone}
                      onChange={(e) => setTimezone(e.target.value)}
                      placeholder="e.g. Asia/Riyadh"
                    />
                  </div>
                </div>

                <SheetFooter>
                  <Button
                    type="button"
                    disabled={!canWrite || createM.isPending || !companyId}
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
              chips={
                <div className="flex items-center gap-2">
                  <div className="text-xs text-text-2">Company</div>
                  <select
                    className={cn(selectClassName, "h-9 py-1")}
                    value={filterCompanyId ?? ""}
                    onChange={(e) => setFilterCompanyId((e.target.value as UUID) || null)}
                    disabled={companiesQ.isLoading || Boolean(companiesQ.error)}
                  >
                    <option value="">All</option>
                    {companyOptions.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.label}
                      </option>
                    ))}
                  </select>
                </div>
              }
              onClearAll={() => setFilterCompanyId(null)}
              clearDisabled={!filterCompanyId}
            />
          }
          isLoading={branchesQ.isLoading || companiesQ.isLoading}
          error={branchesQ.error ?? companiesQ.error}
          onRetry={() => {
            void companiesQ.refetch();
            void branchesQ.refetch();
          }}
          isEmpty={
            noCompanies ||
            (!branchesQ.isLoading && !branchesQ.error && branches.length === 0)
          }
          emptyState={
            noCompanies ? (
              <EmptyState
                title="Create a company first"
                description="Branches require a company. Create your first company from Organization → Companies."
              />
            ) : (
              <EmptyState
                title="No branches yet"
                description="Create your first branch to start enrolling employees and running attendance."
                primaryAction={
                  canWrite ? (
                    <Button type="button" onClick={() => setOpen(true)}>
                      Create branch
                    </Button>
                  ) : null
                }
              />
            )
          }
          skeleton={{ rows: 6, cols: 5 }}
        >
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Code</TableHead>
                <TableHead>Company</TableHead>
                <TableHead>Timezone</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {branches.map((b) => (
                <TableRow key={b.id}>
                  <TableCell className="font-medium">{b.name}</TableCell>
                  <TableCell className="text-text-2">{b.code}</TableCell>
                  <TableCell className="text-text-2">
                    {companyNameById.get(b.company_id) ?? b.company_id}
                  </TableCell>
                  <TableCell className="text-text-2">{b.timezone ?? "—"}</TableCell>
                  <TableCell className="text-text-2">{b.status}</TableCell>
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
              About branches
            </div>
            <div className="mt-2 text-sm text-text-2">
              Branches represent operational locations (e.g. Riyadh HQ, Jeddah store).
              Cameras, employees, shifts, and attendance operations are typically branch-scoped.
            </div>
          </DSCard>
          <DSCard surface="panel" className="p-[var(--ds-space-20)]">
            <div className="text-sm font-semibold tracking-tight text-text-1">
              Summary
            </div>
            <div className="mt-2 grid grid-cols-2 gap-3 text-sm">
              <div className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-3">
                <div className="text-xs text-text-2">branches</div>
                <div className="mt-1 text-lg font-semibold text-text-1">
                  {branches.length}
                </div>
              </div>
              <div className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-3">
                <div className="text-xs text-text-2">filter</div>
                <div className="mt-1 text-sm font-medium text-text-1">
                  {filterCompanyId ? "Company" : "All"}
                </div>
              </div>
            </div>
          </DSCard>
        </RightPanelStack>
      }
    />
  );
}

