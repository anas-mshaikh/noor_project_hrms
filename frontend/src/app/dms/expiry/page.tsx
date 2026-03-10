"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";

import { useAuth } from "@/lib/auth";
import { listExpiryRules, listUpcomingExpiry } from "@/features/dms/api/dms";
import { expiryBucket, expiryLabel } from "@/features/dms/expiry";
import { dmsKeys } from "@/features/dms/queryKeys";
import { compatibilityDocHref } from "@/features/dms/routes";

import { DataTable } from "@/components/ds/DataTable";
import { DSCard } from "@/components/ds/DSCard";
import { EmptyState } from "@/components/ds/EmptyState";
import { ErrorState } from "@/components/ds/ErrorState";
import { FilterBar } from "@/components/ds/FilterBar";
import { PageHeader } from "@/components/ds/PageHeader";
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

const DAY_OPTIONS = [7, 15, 30] as const;

function formatDate(value: string): string {
  try {
    return new Date(value).toLocaleDateString();
  } catch {
    return value;
  }
}

export default function DmsExpiryPage() {
  const permissions = useAuth((s) => s.permissions);
  const granted = React.useMemo(() => new Set(permissions ?? []), [permissions]);
  const canReadExpiry = granted.has("dms:expiry:read") || granted.has("dms:expiry:write");

  const [days, setDays] = React.useState<(typeof DAY_OPTIONS)[number]>(30);
  const [selectedId, setSelectedId] = React.useState<string | null>(null);

  const upcomingQ = useQuery({
    queryKey: dmsKeys.expiryUpcoming(days),
    enabled: canReadExpiry,
    queryFn: () => listUpcomingExpiry(days),
  });

  const rulesQ = useQuery({
    queryKey: dmsKeys.expiryRules(),
    enabled: canReadExpiry,
    queryFn: () => listExpiryRules(),
  });

  const items = React.useMemo(() => upcomingQ.data?.items ?? [], [upcomingQ.data]);
  const selected = items.find((item) => item.document_id === selectedId) ?? items[0] ?? null;

  React.useEffect(() => {
    if (selectedId) return;
    if (items.length > 0) setSelectedId(items[0].document_id);
  }, [items, selectedId]);

  const counts = React.useMemo(() => {
    return items.reduce(
      (acc, item) => {
        acc[expiryBucket(item.days_left)] += 1;
        return acc;
      },
      { expired: 0, today: 0, week: 0, month: 0, later: 0 },
    );
  }, [items]);

  if (!canReadExpiry) {
    return (
      <ErrorState
        title="Access denied"
        error={new Error("Your account does not have access to DMS expiry reporting.")}
      />
    );
  }

  return (
    <ListRightPanelTemplate
      header={<PageHeader title="Expiring Docs" subtitle="Documents expiring in the selected horizon." />}
      main={
        <DataTable
          toolbar={
            <FilterBar
              chips={
                <div className="flex flex-wrap gap-2">
                  {DAY_OPTIONS.map((option) => (
                    <Button
                      key={option}
                      type="button"
                      variant={option === days ? "default" : "outline"}
                      onClick={() => setDays(option)}
                    >
                      {option} days
                    </Button>
                  ))}
                </div>
              }
            />
          }
          isLoading={upcomingQ.isLoading}
          error={upcomingQ.error}
          onRetry={upcomingQ.refetch}
          isEmpty={!upcomingQ.isLoading && !upcomingQ.error && items.length === 0}
          emptyState={
            <EmptyState
              title="No upcoming expiries"
              description="No documents are expiring in the selected horizon."
              align="center"
            />
          }
          skeleton={{ rows: 6, cols: 4 }}
        >
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Type</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Expiry</TableHead>
                <TableHead>Days left</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((item) => (
                <TableRow key={item.document_id} className="cursor-pointer" onClick={() => setSelectedId(item.document_id)}>
                  <TableCell>
                    <div className="font-medium text-text-1">{item.document_type_name}</div>
                    <div className="mt-1 text-xs text-text-3">{item.document_type_code}</div>
                  </TableCell>
                  <TableCell>
                    <StatusChip status={item.status} />
                  </TableCell>
                  <TableCell className="text-text-2">{formatDate(item.expires_at)}</TableCell>
                  <TableCell className="text-text-2">{item.days_left}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </DataTable>
      }
      right={
        <div className="space-y-4">
          <DSCard surface="panel" className="p-[var(--ds-space-16)]">
            <div className="text-sm font-medium text-text-1">Buckets</div>
            <div className="mt-3 grid gap-3 text-sm md:grid-cols-2 lg:grid-cols-1">
              <div className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-3">Today: {counts.today}</div>
              <div className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-3">This week: {counts.week}</div>
              <div className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-3">This month: {counts.month}</div>
              <div className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-3">Later: {counts.later}</div>
            </div>
          </DSCard>

          <DSCard surface="panel" className="p-[var(--ds-space-16)]">
            <div className="text-sm font-medium text-text-1">Selected document</div>
            {selected ? (
              <div className="mt-3 space-y-3 text-sm">
                <div className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-3">
                  <div className="text-xs text-text-2">Document type</div>
                  <div className="mt-1 text-text-1">{selected.document_type_name}</div>
                </div>
                <div className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-3">
                  <div className="text-xs text-text-2">Expiry</div>
                  <div className="mt-1 text-text-1">{formatDate(selected.expires_at)}</div>
                  <div className="mt-1 text-xs text-text-3">{expiryLabel(selected.days_left)}</div>
                </div>
                <Button asChild type="button" variant="secondary">
                  <Link href={compatibilityDocHref({ docId: selected.document_id, employeeId: selected.owner_employee_id })}>
                    Open document
                  </Link>
                </Button>
              </div>
            ) : (
              <div className="mt-3 text-sm text-text-3">Select a document to inspect expiry details.</div>
            )}
          </DSCard>

          <DSCard surface="panel" className="p-[var(--ds-space-16)]">
            <div className="text-sm font-medium text-text-1">Expiry rules</div>
            {rulesQ.isLoading ? (
              <div className="mt-3 text-sm text-text-3">Loading...</div>
            ) : rulesQ.isError ? (
              <ErrorState title="Could not load expiry rules" error={rulesQ.error} onRetry={rulesQ.refetch} variant="inline" className="mt-3 max-w-none" />
            ) : rulesQ.data?.items.length ? (
              <div className="mt-3 space-y-2 text-sm">
                {rulesQ.data.items.map((rule) => (
                  <div key={rule.id} className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-3">
                    <div className="font-medium text-text-1">{rule.document_type_name ?? rule.document_type_code ?? "Unknown type"}</div>
                    <div className="mt-1 text-xs text-text-2">Notify {rule.days_before} days before expiry</div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="mt-3 text-sm text-text-3">No expiry rules configured.</div>
            )}
          </DSCard>
        </div>
      }
    />
  );
}
