"use client";

import * as React from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/lib/auth";
import { useSelection } from "@/lib/selection";
import { toastApiError } from "@/lib/toastApiError";
import type { OrgUnitCreate, OrgUnitOut, UUID } from "@/lib/types";
import { createOrgUnit, listOrgUnits } from "@/features/tenancy/api/tenancy";
import { tenancyKeys } from "@/features/tenancy/queryKeys";

import { DataTable } from "@/components/ds/DataTable";
import { DSCard } from "@/components/ds/DSCard";
import { EmptyState } from "@/components/ds/EmptyState";
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

type OrgUnitRow = { unit: OrgUnitOut; depth: number };

function buildOrgUnitRows(units: OrgUnitOut[]): OrgUnitRow[] {
  /**
   * Build a stable, indented row list from a parent_id hierarchy.
   *
   * Notes:
   * - Sort by name for deterministic UI.
   * - Orphans (missing parent) and cycles are appended defensively.
   */
  const byParent = new Map<string | null, OrgUnitOut[]>();
  const byId = new Map<string, OrgUnitOut>();
  for (const u of units) {
    byId.set(u.id, u);
    const key = u.parent_id ?? null;
    const arr = byParent.get(key) ?? [];
    arr.push(u);
    byParent.set(key, arr);
  }
  for (const arr of byParent.values()) {
    arr.sort((a, b) => a.name.localeCompare(b.name));
  }

  const out: OrgUnitRow[] = [];
  const seen = new Set<string>();
  const walk = (parentId: string | null, depth: number) => {
    const kids = byParent.get(parentId) ?? [];
    for (const k of kids) {
      if (seen.has(k.id)) continue;
      seen.add(k.id);
      out.push({ unit: k, depth });
      walk(k.id, depth + 1);
    }
  };

  // Normal roots.
  walk(null, 0);

  // Orphans / cycles.
  const remaining = units
    .filter((u) => !seen.has(u.id))
    .sort((a, b) => a.name.localeCompare(b.name));
  for (const u of remaining) out.push({ unit: u, depth: 0 });

  return out;
}

export default function OrgUnitsPage() {
  const companyId = useSelection((s) => s.companyId);
  const branchId = useSelection((s) => s.branchId);

  const permissions = useAuth((s) => s.permissions);
  const canWrite = React.useMemo(
    () => new Set(permissions ?? []).has("tenancy:write"),
    [permissions]
  );

  const qc = useQueryClient();

  const unitsQ = useQuery({
    queryKey: companyId
      ? tenancyKeys.orgUnits({ companyId, branchId })
      : ["tenancy", "org-units", "missing-company"],
    enabled: Boolean(companyId),
    queryFn: () =>
      listOrgUnits({
        companyId: companyId as UUID,
        branchId: branchId ?? null,
      }),
  });

  const units = (unitsQ.data ?? []) as OrgUnitOut[];
  const rows = React.useMemo(() => buildOrgUnitRows(units), [units]);
  const topLevelCount = React.useMemo(
    () => units.filter((u) => !u.parent_id).length,
    [units]
  );

  const [open, setOpen] = React.useState(false);
  const [name, setName] = React.useState("");
  const [unitType, setUnitType] = React.useState("");
  const [parentId, setParentId] = React.useState<UUID | "">("");

  const createM = useMutation({
    mutationFn: async () => {
      if (!companyId) throw new Error("Company selection is required.");

      const payload: OrgUnitCreate = {
        company_id: companyId,
        branch_id: branchId ?? null,
        parent_id: parentId ? parentId : null,
        name: name.trim(),
        unit_type: unitType.trim() ? unitType.trim() : null,
      };
      if (!payload.name) throw new Error("Org unit name is required.");
      return createOrgUnit(payload);
    },
    onSuccess: async () => {
      setOpen(false);
      setName("");
      setUnitType("");
      setParentId("");
      if (companyId) {
        await qc.invalidateQueries({
          queryKey: tenancyKeys.orgUnits({ companyId, branchId }),
        });
      }
    },
    onError: (err) => toastApiError(err),
  });

  if (!companyId) {
    return (
      <EmptyState
        title="Select a company"
        description="Org units are company-scoped. Select a company from the scope picker to continue."
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
          title="Org Units"
          subtitle="Define your org structure (departments, teams, locations)."
          actions={
            <Sheet open={open} onOpenChange={setOpen}>
              <SheetTrigger asChild>
                <Button type="button" disabled={!canWrite}>
                  Create unit
                </Button>
              </SheetTrigger>
              <SheetContent className="border-border-subtle bg-surface-2 backdrop-blur-xl">
                <SheetHeader>
                  <SheetTitle>Create org unit</SheetTitle>
                  <SheetDescription>
                    Units can be company-wide or branch-specific based on your current scope.
                  </SheetDescription>
                </SheetHeader>

                <div className="space-y-4 px-4">
                  <div className="space-y-1">
                    <Label htmlFor="org-unit-name" className="text-xs text-text-2">
                      Name
                    </Label>
                    <Input
                      id="org-unit-name"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                    />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="org-unit-type" className="text-xs text-text-2">
                      Unit type (optional)
                    </Label>
                    <Input
                      id="org-unit-type"
                      value={unitType}
                      onChange={(e) => setUnitType(e.target.value)}
                      placeholder="e.g. Department"
                    />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="org-unit-parent" className="text-xs text-text-2">
                      Parent (optional)
                    </Label>
                    <select
                      id="org-unit-parent"
                      className="h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                      value={parentId}
                      onChange={(e) => setParentId((e.target.value as UUID) || "")}
                      disabled={unitsQ.isLoading || units.length === 0}
                    >
                      <option value="">None</option>
                      {rows.map((r) => (
                        <option key={r.unit.id} value={r.unit.id}>
                          {"  ".repeat(Math.min(r.depth, 6))}
                          {r.unit.name}
                        </option>
                      ))}
                    </select>
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
          isLoading={unitsQ.isLoading}
          error={unitsQ.error}
          onRetry={unitsQ.refetch}
          isEmpty={!unitsQ.isLoading && !unitsQ.error && rows.length === 0}
          emptyState={
            <EmptyState
              title="No org units yet"
              description="Create your first org unit to build reporting structure and assignment policies."
              primaryAction={
                canWrite ? (
                  <Button type="button" onClick={() => setOpen(true)}>
                    Create unit
                  </Button>
                ) : null
              }
            />
          }
          skeleton={{ rows: 6, cols: 4 }}
        >
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Scope</TableHead>
                <TableHead>Parent</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map(({ unit, depth }) => (
                <TableRow key={unit.id}>
                  <TableCell className="font-medium">
                    <div style={{ paddingInlineStart: depth * 14 }}>
                      {unit.name}
                    </div>
                  </TableCell>
                  <TableCell className="text-text-2">{unit.unit_type ?? "—"}</TableCell>
                  <TableCell className="text-text-2">
                    {unit.branch_id ? "Branch" : "Company"}
                  </TableCell>
                  <TableCell className="text-text-2">
                    {unit.parent_id
                      ? units.find((u) => u.id === unit.parent_id)?.name ?? unit.parent_id
                      : "—"}
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
              Tips
            </div>
            <div className="mt-2 space-y-2 text-sm text-text-2">
              <div>
                Use top-level units for major divisions (e.g. Sales, Ops, HQ).
              </div>
              <div>
                Keep unit types lightweight (department, team, location). Policy rules will be added later.
              </div>
            </div>
          </DSCard>

          <DSCard surface="panel" className="p-[var(--ds-space-20)]">
            <div className="text-sm font-semibold tracking-tight text-text-1">
              Summary
            </div>
            <div className="mt-2 grid grid-cols-2 gap-3 text-sm">
              <div className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-3">
                <div className="text-xs text-text-2">units</div>
                <div className="mt-1 text-lg font-semibold text-text-1">
                  {units.length}
                </div>
              </div>
              <div className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-3">
                <div className="text-xs text-text-2">top-level</div>
                <div className="mt-1 text-lg font-semibold text-text-1">
                  {topLevelCount}
                </div>
              </div>
            </div>
          </DSCard>
        </RightPanelStack>
      }
    />
  );
}

