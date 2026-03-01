"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";

import { useSelection } from "@/lib/selection";
import type { OrgUnitNode, UUID } from "@/lib/types";
import { getOrgChart } from "@/features/tenancy/api/tenancy";
import { tenancyKeys } from "@/features/tenancy/queryKeys";

import { DataTable } from "@/components/ds/DataTable";
import { DSCard } from "@/components/ds/DSCard";
import { EmptyState } from "@/components/ds/EmptyState";
import { PageHeader } from "@/components/ds/PageHeader";
import { RightPanelStack } from "@/components/ds/RightPanelStack";
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

type NodeRow = { node: OrgUnitNode; depth: number };

function flatten(nodes: OrgUnitNode[], depth = 0, out: NodeRow[] = []): NodeRow[] {
  for (const n of nodes) {
    out.push({ node: n, depth });
    if (n.children?.length) flatten(n.children, depth + 1, out);
  }
  return out;
}

function countNodes(nodes: OrgUnitNode[]): number {
  return flatten(nodes).length;
}

export default function OrgChartPage() {
  const companyId = useSelection((s) => s.companyId);
  const branchId = useSelection((s) => s.branchId);

  const chartQ = useQuery({
    queryKey: companyId
      ? tenancyKeys.orgChart({ companyId, branchId })
      : ["tenancy", "org-chart", "missing-company"],
    enabled: Boolean(companyId),
    queryFn: () =>
      getOrgChart({
        companyId: companyId as UUID,
        branchId: branchId ?? null,
      }),
  });

  const nodes = (chartQ.data ?? []) as OrgUnitNode[];
  const rows = React.useMemo(() => flatten(nodes), [nodes]);
  const total = React.useMemo(() => countNodes(nodes), [nodes]);

  const [selectedId, setSelectedId] = React.useState<string | null>(null);
  const selected = React.useMemo(() => {
    if (!selectedId) return null;
    return rows.find((r) => r.node.id === selectedId)?.node ?? null;
  }, [rows, selectedId]);

  if (!companyId) {
    return (
      <EmptyState
        title="Select a company"
        description="Org chart is company-scoped. Select a company from the scope picker to continue."
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
          title="Org Chart"
          subtitle={
            branchId
              ? "Org chart viewer for the selected company + branch."
              : "Org chart viewer for the selected company."
          }
        />
      }
      main={
        <DataTable
          isLoading={chartQ.isLoading}
          error={chartQ.error}
          onRetry={chartQ.refetch}
          isEmpty={!chartQ.isLoading && !chartQ.error && rows.length === 0}
          emptyState={
            <EmptyState
              title="No org units yet"
              description="Create org units first, then come back to view the chart."
              primaryAction={
                <Button asChild type="button">
                  <Link href="/settings/org/org-units">Go to org units</Link>
                </Button>
              }
            />
          }
          skeleton={{ rows: 6, cols: 3 }}
        >
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Unit</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Children</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map(({ node, depth }) => {
                const active = node.id === selectedId;
                return (
                  <TableRow
                    key={node.id}
                    className={active ? "bg-muted/40" : "cursor-pointer"}
                    onClick={() => setSelectedId(node.id)}
                    aria-selected={active}
                  >
                    <TableCell className="font-medium">
                      <div style={{ paddingInlineStart: depth * 14 }}>
                        {node.name}
                      </div>
                    </TableCell>
                    <TableCell className="text-text-2">{node.unit_type ?? "—"}</TableCell>
                    <TableCell className="text-text-2">{node.children?.length ?? 0}</TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </DataTable>
      }
      right={
        <RightPanelStack>
          <DSCard surface="panel" className="p-[var(--ds-space-20)]">
            <div className="text-sm font-semibold tracking-tight text-text-1">
              Selected unit
            </div>
            {selected ? (
              <div className="mt-2 space-y-2 text-sm text-text-2">
                <div>
                  <span className="text-text-3">name</span>:{" "}
                  <span className="text-text-1">{selected.name}</span>
                </div>
                <div>
                  <span className="text-text-3">type</span>:{" "}
                  <span className="text-text-1">{selected.unit_type ?? "—"}</span>
                </div>
                <div>
                  <span className="text-text-3">children</span>:{" "}
                  <span className="text-text-1">{selected.children?.length ?? 0}</span>
                </div>
              </div>
            ) : (
              <div className="mt-2 text-sm text-text-2">
                Click a unit on the left to see details.
              </div>
            )}
          </DSCard>

          <DSCard surface="panel" className="p-[var(--ds-space-20)]">
            <div className="text-sm font-semibold tracking-tight text-text-1">
              Summary
            </div>
            <div className="mt-2 grid grid-cols-2 gap-3 text-sm">
              <div className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-3">
                <div className="text-xs text-text-2">units</div>
                <div className="mt-1 text-lg font-semibold text-text-1">{total}</div>
              </div>
              <div className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-3">
                <div className="text-xs text-text-2">scope</div>
                <div className="mt-1 text-sm font-medium text-text-1">
                  {branchId ? "Branch" : "Company"}
                </div>
              </div>
            </div>
          </DSCard>
        </RightPanelStack>
      }
    />
  );
}

