"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";

import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useSelection } from "@/lib/selection";
import { cn } from "@/lib/utils";
import type { BranchOut, MssEmployeeSummaryOut, OrgUnitOut, UUID } from "@/lib/types";
import { listBranches, listOrgUnits } from "@/features/tenancy/api/tenancy";
import { tenancyKeys } from "@/features/tenancy/queryKeys";
import { listTeam } from "@/features/mss/api/mss";
import { mssKeys } from "@/features/mss/queryKeys";

import { DataTable } from "@/components/ds/DataTable";
import { DSCard } from "@/components/ds/DSCard";
import { EmptyState } from "@/components/ds/EmptyState";
import { ErrorState } from "@/components/ds/ErrorState";
import { FilterBar } from "@/components/ds/FilterBar";
import { PageHeader } from "@/components/ds/PageHeader";
import { RightPanelStack } from "@/components/ds/RightPanelStack";
import { StatusChip } from "@/components/ds/StatusChip";
import { ListRightPanelTemplate } from "@/components/ds/templates/ListRightPanelTemplate";
import { Button } from "@/components/ui/button";
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

export default function MssTeamPage() {
  const permissions = useAuth((s) => s.permissions);
  const permSet = React.useMemo(() => new Set(permissions ?? []), [permissions]);
  const canReadTenancy = permSet.has("tenancy:read") || permSet.has("tenancy:write");

  const companyId = useSelection((s) => s.companyId);

  const [depth, setDepth] = React.useState<"1" | "all">("1");
  const [q, setQ] = React.useState("");
  const [status, setStatus] = React.useState("");
  const [branchId, setBranchId] = React.useState<UUID | "">("");
  const [orgUnitId, setOrgUnitId] = React.useState<UUID | "">("");
  const [limit, setLimit] = React.useState(25);
  const [offset, setOffset] = React.useState(0);

  React.useEffect(() => {
    setOffset(0);
  }, [depth, q, status, branchId, orgUnitId, limit]);

  const branchesQ = useQuery({
    queryKey: tenancyKeys.branches(companyId ?? null),
    enabled: Boolean(companyId && canReadTenancy),
    queryFn: () => listBranches({ companyId: companyId as UUID }),
  });
  const branches = (branchesQ.data ?? []) as BranchOut[];

  const orgUnitsQ = useQuery({
    queryKey: companyId
      ? tenancyKeys.orgUnits({ companyId: companyId as UUID, branchId: branchId || null })
      : ["tenancy", "org-units", "missing-company"],
    enabled: Boolean(companyId && canReadTenancy),
    queryFn: () =>
      listOrgUnits({
        companyId: companyId as UUID,
        branchId: branchId || null,
      }),
  });
  const orgUnits = (orgUnitsQ.data ?? []) as OrgUnitOut[];

  const teamQ = useQuery({
    queryKey: mssKeys.team({
      depth,
      q: q.trim() ? q.trim() : null,
      status: status || null,
      branchId: branchId || null,
      orgUnitId: orgUnitId || null,
      limit,
      offset,
    }),
    queryFn: () =>
      listTeam({
        depth,
        q: q.trim() ? q.trim() : null,
        status: status || null,
        branchId: branchId || null,
        orgUnitId: orgUnitId || null,
        limit,
        offset,
      }),
  });

  const items = (teamQ.data?.items ?? []) as MssEmployeeSummaryOut[];
  const paging = teamQ.data?.paging ?? { limit, offset, total: 0 };
  const total = paging.total ?? 0;
  const canPrev = offset > 0;
  const canNext = offset + limit < total;

  const selectClassName = cn(
    "h-10 rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm",
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
    "disabled:cursor-not-allowed disabled:opacity-50"
  );

  if (teamQ.error instanceof ApiError && (teamQ.error.code === "mss.not_linked" || teamQ.error.code === "mss.no_current_employment")) {
    return <ErrorState title="Team not available" error={teamQ.error} />;
  }

  return (
    <ListRightPanelTemplate
      header={
        <PageHeader
          title="My Team"
          subtitle="Direct reports and org hierarchy visibility."
        />
      }
      main={
        <DataTable
          toolbar={
            <FilterBar
              search={{
                value: q,
                onChange: setQ,
                placeholder: "Search team…",
              }}
              chips={
                <div className="flex flex-wrap items-center gap-3">
                  <div className="flex items-center gap-2">
                    <div className="text-xs text-text-2">Depth</div>
                    <select
                      aria-label="Depth"
                      className={cn(selectClassName, "h-9 py-1")}
                      value={depth}
                      onChange={(e) => setDepth(e.target.value as "1" | "all")}
                    >
                      <option value="1">Direct</option>
                      <option value="all">All</option>
                    </select>
                  </div>

                  <div className="flex items-center gap-2">
                    <div className="text-xs text-text-2">Status</div>
                    <select
                      aria-label="Status"
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

                  {canReadTenancy && companyId ? (
                    <div className="flex items-center gap-2">
                      <div className="text-xs text-text-2">Branch</div>
                      <select
                        aria-label="Branch"
                        className={cn(selectClassName, "h-9 py-1")}
                        value={branchId}
                        onChange={(e) => setBranchId(e.target.value as UUID)}
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

                  {canReadTenancy && companyId ? (
                    <div className="flex items-center gap-2">
                      <div className="text-xs text-text-2">Org unit</div>
                      <select
                        aria-label="Org unit"
                        className={cn(selectClassName, "h-9 py-1")}
                        value={orgUnitId}
                        onChange={(e) => setOrgUnitId(e.target.value as UUID)}
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
                    aria-label="Page size"
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
                setDepth("1");
                setQ("");
                setStatus("");
                setBranchId("");
                setOrgUnitId("");
              }}
              clearDisabled={!q && !status && !branchId && !orgUnitId && depth === "1"}
            />
          }
          isLoading={teamQ.isLoading}
          error={teamQ.error}
          onRetry={teamQ.refetch}
          isEmpty={!teamQ.isLoading && !teamQ.error && items.length === 0}
          emptyState={
            <EmptyState
              title="No team members"
              description="No employees were returned for the selected filters."
            />
          }
          skeleton={{ rows: 7, cols: 5 }}
        >
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Code</TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Depth</TableHead>
                <TableHead>Manager</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((e) => (
                <TableRow key={e.employee_id}>
                  <TableCell className="font-medium">
                    <Link href={`/mss/team/${e.employee_id}`} className="hover:underline">
                      {e.employee_code}
                    </Link>
                  </TableCell>
                  <TableCell className="text-text-1">{e.display_name}</TableCell>
                  <TableCell>
                    <StatusChip status={e.status} />
                  </TableCell>
                  <TableCell className="text-text-2">{e.relationship_depth}</TableCell>
                  <TableCell className="text-text-2">{formatId(e.manager_employee_id)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </DataTable>
      }
      right={
        <RightPanelStack>
          <DSCard surface="panel" className="p-[var(--ds-space-20)]">
            <div className="text-sm font-semibold tracking-tight text-text-1">Summary</div>
            <div className="mt-2 grid grid-cols-2 gap-3 text-sm">
              <div className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-3">
                <div className="text-xs text-text-2">members</div>
                <div className="mt-1 text-lg font-semibold text-text-1">{total}</div>
              </div>
              <div className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-3">
                <div className="text-xs text-text-2">depth</div>
                <div className="mt-1 text-lg font-semibold text-text-1">{depth}</div>
              </div>
            </div>
          </DSCard>
        </RightPanelStack>
      }
    />
  );
}
