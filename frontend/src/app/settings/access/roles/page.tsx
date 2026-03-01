"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";

import type { RoleOut } from "@/lib/types";
import { listRoles } from "@/features/iam/api/iam";
import { iamKeys } from "@/features/iam/queryKeys";

import { DataTable } from "@/components/ds/DataTable";
import { DSCard } from "@/components/ds/DSCard";
import { EmptyState } from "@/components/ds/EmptyState";
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

export default function RolesPage() {
  const rolesQ = useQuery({
    queryKey: iamKeys.roles(),
    queryFn: () => listRoles(),
  });

  const roles = (rolesQ.data ?? []) as RoleOut[];

  return (
    <ListRightPanelTemplate
      header={<PageHeader title="Roles" subtitle="Role catalog (read-only)." />}
      main={
        <DataTable
          isLoading={rolesQ.isLoading}
          error={rolesQ.error}
          onRetry={rolesQ.refetch}
          isEmpty={!rolesQ.isLoading && !rolesQ.error && roles.length === 0}
          emptyState={
            <EmptyState
              title="No roles"
              description="Roles are seeded by migrations. If this is empty, check seeds/migrations for your environment."
            />
          }
          skeleton={{ rows: 8, cols: 3 }}
        >
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Code</TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Description</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {roles.map((r) => (
                <TableRow key={r.code}>
                  <TableCell className="font-mono text-xs text-text-3">{r.code}</TableCell>
                  <TableCell className="font-medium">{r.name}</TableCell>
                  <TableCell className="text-text-2">{r.description ?? "—"}</TableCell>
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
              Notes
            </div>
            <div className="mt-2 text-sm text-text-2">
              Roles are assigned to users with tenant/company/branch scope. Use the Users page to add or remove assignments.
            </div>
          </DSCard>

          <DSCard surface="panel" className="p-[var(--ds-space-20)]">
            <div className="text-sm font-semibold tracking-tight text-text-1">
              Summary
            </div>
            <div className="mt-2 grid grid-cols-2 gap-3 text-sm">
              <div className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-3">
                <div className="text-xs text-text-2">roles</div>
                <div className="mt-1 text-lg font-semibold text-text-1">
                  {roles.length}
                </div>
              </div>
              <div className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-3">
                <div className="text-xs text-text-2">mode</div>
                <div className="mt-1 text-sm font-medium text-text-1">Read-only</div>
              </div>
            </div>
          </DSCard>
        </RightPanelStack>
      }
    />
  );
}

