"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";

import type { PermissionOut } from "@/lib/types";
import { listPermissions } from "@/features/iam/api/iam";
import { iamKeys } from "@/features/iam/queryKeys";

import { DataTable } from "@/components/ds/DataTable";
import { DSCard } from "@/components/ds/DSCard";
import { EmptyState } from "@/components/ds/EmptyState";
import { FilterBar } from "@/components/ds/FilterBar";
import { PageHeader } from "@/components/ds/PageHeader";
import { RightPanelStack } from "@/components/ds/RightPanelStack";
import { ListRightPanelTemplate } from "@/components/ds/templates/ListRightPanelTemplate";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

function groupByPrefix(items: PermissionOut[]): Array<{ prefix: string; items: PermissionOut[] }> {
  const by = new Map<string, PermissionOut[]>();
  for (const p of items) {
    const prefix = (p.code.split(":")[0] ?? "other").trim() || "other";
    const arr = by.get(prefix) ?? [];
    arr.push(p);
    by.set(prefix, arr);
  }
  const groups = Array.from(by.entries()).map(([prefix, list]) => ({
    prefix,
    items: list.sort((a, b) => a.code.localeCompare(b.code)),
  }));
  groups.sort((a, b) => a.prefix.localeCompare(b.prefix));
  return groups;
}

export default function PermissionsPage() {
  const [q, setQ] = React.useState("");

  const permsQ = useQuery({
    queryKey: iamKeys.permissions(),
    queryFn: () => listPermissions(),
  });

  const all = (permsQ.data ?? []) as PermissionOut[];
  const filtered = React.useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return all;
    return all.filter((p) => p.code.toLowerCase().includes(needle));
  }, [all, q]);

  const grouped = React.useMemo(() => groupByPrefix(filtered), [filtered]);

  return (
    <ListRightPanelTemplate
      header={
        <PageHeader
          title="Permissions"
          subtitle="Permission catalog (read-only)."
        />
      }
      main={
        <DataTable
          toolbar={
            <FilterBar
              search={{
                value: q,
                onChange: setQ,
                placeholder: "Search permission codes...",
                disabled: permsQ.isLoading,
              }}
              onClearAll={() => setQ("")}
              clearDisabled={!q.trim()}
            />
          }
          isLoading={permsQ.isLoading}
          error={permsQ.error}
          onRetry={permsQ.refetch}
          isEmpty={!permsQ.isLoading && !permsQ.error && filtered.length === 0}
          emptyState={
            <EmptyState
              title={q.trim() ? "No matches" : "No permissions"}
              description={
                q.trim()
                  ? "Try a different search term."
                  : "Permissions are seeded by migrations. If this is empty, check seeds/migrations for your environment."
              }
            />
          }
          skeleton={{ rows: 10, cols: 2 }}
        >
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Code</TableHead>
                <TableHead>Description</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {grouped.map((g) => (
                <React.Fragment key={g.prefix}>
                  <TableRow className="bg-muted/30">
                    <TableCell colSpan={2} className="py-2 text-xs font-semibold text-text-2">
                      {g.prefix} <span className="text-text-3">({g.items.length})</span>
                    </TableCell>
                  </TableRow>
                  {g.items.map((p) => (
                    <TableRow key={p.code}>
                      <TableCell className="font-mono text-xs text-text-3">
                        {p.code}
                      </TableCell>
                      <TableCell className="text-text-2">
                        {p.description ?? "—"}
                      </TableCell>
                    </TableRow>
                  ))}
                </React.Fragment>
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
                Permissions are evaluated together with a user’s scoped role assignments (tenant/company/branch).
              </div>
              <div>
                For security, UI gating is only a convenience; backend RBAC is always authoritative.
              </div>
            </div>
          </DSCard>

          <DSCard surface="panel" className="p-[var(--ds-space-20)]">
            <div className="text-sm font-semibold tracking-tight text-text-1">
              Summary
            </div>
            <div className="mt-2 grid grid-cols-2 gap-3 text-sm">
              <div className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-3">
                <div className="text-xs text-text-2">visible</div>
                <div className="mt-1 text-lg font-semibold text-text-1">
                  {filtered.length}
                </div>
              </div>
              <div className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-3">
                <div className="text-xs text-text-2">groups</div>
                <div className="mt-1 text-lg font-semibold text-text-1">
                  {grouped.length}
                </div>
              </div>
            </div>
          </DSCard>
        </RightPanelStack>
      }
    />
  );
}

