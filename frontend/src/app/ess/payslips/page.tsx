"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useMutation } from "@tanstack/react-query";

import { saveBlobAsFile } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { parseUuidParam } from "@/lib/guards";
import { toastApiError } from "@/lib/toastApiError";
import type { PayslipOut, UUID } from "@/lib/types";
import { downloadMyPayslip } from "@/features/payroll/api/payroll";
import { useMyPayslip, useMyPayslips } from "@/features/payroll/hooks";

import { DataTable } from "@/components/ds/DataTable";
import { DSCard } from "@/components/ds/DSCard";
import { EmptyState } from "@/components/ds/EmptyState";
import { ErrorState } from "@/components/ds/ErrorState";
import { FilterBar } from "@/components/ds/FilterBar";
import { PageHeader } from "@/components/ds/PageHeader";
import { StatusChip } from "@/components/ds/StatusChip";
import { ListRightPanelTemplate } from "@/components/ds/templates/ListRightPanelTemplate";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

function formatDateTime(value: string): string {
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

function payslipHref(payslipId?: UUID | null, year?: number): string {
  const params = new URLSearchParams();
  if (payslipId) params.set("payslipId", payslipId);
  if (year) params.set("year", String(year));
  const qs = params.toString();
  return qs ? `/ess/payslips?${qs}` : "/ess/payslips";
}

export default function EssPayslipsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const permissions = useAuth((s) => s.permissions);
  const granted = React.useMemo(() => new Set(permissions ?? []), [permissions]);
  const canRead = granted.has("payroll:payslip:read");

  const nowYear = new Date().getFullYear();
  const yearParam = Number(searchParams.get("year") ?? nowYear);
  const year = Number.isFinite(yearParam) ? yearParam : nowYear;
  const payslipId = parseUuidParam(searchParams.get("payslipId"));

  const payslipsQ = useMyPayslips(year, canRead);
  const detailQ = useMyPayslip(payslipId, Boolean(canRead && payslipId));

  const items = React.useMemo(() => payslipsQ.data?.items ?? [], [payslipsQ.data]);
  const selected = React.useMemo<PayslipOut | null>(
    () => items.find((item) => item.id === payslipId) ?? detailQ.data ?? null,
    [detailQ.data, items, payslipId],
  );

  React.useEffect(() => {
    if (!payslipId && items[0]) {
      router.replace(payslipHref(items[0].id, year));
    }
  }, [items, payslipId, router, year]);

  const downloadM = useMutation({
    mutationFn: async (id: UUID) => downloadMyPayslip(id),
    onSuccess: (out) => {
      saveBlobAsFile(out.blob, out.filename);
    },
    onError: (err) => toastApiError(err),
  });

  function setSelected(nextPayslipId: UUID | null) {
    router.push(payslipHref(nextPayslipId, year));
  }

  if (!canRead) {
    return (
      <ErrorState
        title="Access denied"
        error={new Error("Your account does not have access to payslips.")}
      />
    );
  }

  return (
    <ListRightPanelTemplate
      header={<PageHeader title="Payslips" subtitle="Published payroll payslips for your employee profile." />}
      main={
        <DataTable
          toolbar={
            <FilterBar
              chips={
                <div className="flex items-center gap-2">
                  <label htmlFor="payslip-year" className="text-xs text-text-2">
                    Year
                  </label>
                  <input
                    id="payslip-year"
                    type="number"
                    min={2000}
                    max={2100}
                    className="h-9 rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm"
                    value={year}
                    onChange={(event) => {
                      const nextYear = Number(event.target.value) || nowYear;
                      router.push(payslipHref(null, nextYear));
                    }}
                  />
                </div>
              }
            />
          }
          isLoading={payslipsQ.isLoading}
          error={payslipsQ.error}
          onRetry={() => void payslipsQ.refetch()}
          isEmpty={!payslipsQ.isLoading && !payslipsQ.error && items.length === 0}
          emptyState={<EmptyState title="No payslips" description="Published payslips for the selected year will appear here." align="center" />}
          skeleton={{ rows: 6, cols: 4 }}
        >
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Period</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Created</TableHead>
                <TableHead>Updated</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((item) => (
                <TableRow key={item.id} className="cursor-pointer" onClick={() => setSelected(item.id)}>
                  <TableCell className="font-medium">{item.period_key ?? "—"}</TableCell>
                  <TableCell>
                    <StatusChip status={item.status} />
                  </TableCell>
                  <TableCell className="text-text-2">{formatDateTime(item.created_at)}</TableCell>
                  <TableCell className="text-text-2">{formatDateTime(item.updated_at)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </DataTable>
      }
      right={
        detailQ.isError ? (
          <ErrorState
            title="Not found"
            error={new Error("This payslip does not exist or is not accessible.")}
            details={
              <Button asChild variant="secondary">
                <Link href="/ess/payslips">Go to Payslips</Link>
              </Button>
            }
          />
        ) : selected ? (
          <DSCard surface="panel" className="space-y-4 p-[var(--ds-space-16)]">
            <div>
              <div className="text-sm font-semibold tracking-tight text-text-1">Payslip detail</div>
              <div className="mt-1 text-sm text-text-2">{selected.period_key ?? "No period key"}</div>
            </div>
            <div className="flex flex-wrap gap-2">
              <StatusChip status={selected.status} />
            </div>
            <div className="space-y-2 text-sm text-text-2">
              <div>Payrun: {selected.payrun_id}</div>
              <div>DMS document: {selected.dms_document_id ?? "Pending publish"}</div>
              <div>Created: {formatDateTime(selected.created_at)}</div>
              <div>Updated: {formatDateTime(selected.updated_at)}</div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button
                type="button"
                disabled={downloadM.isPending}
                onClick={() => void downloadM.mutateAsync(selected.id)}
              >
                {downloadM.isPending ? "Downloading..." : "Download payslip"}
              </Button>
            </div>
            <div className="text-xs text-text-3">
              Payslips are published as JSON downloads in v1. No PDF preview is rendered in the web app.
            </div>
          </DSCard>
        ) : (
          <EmptyState title="Select a payslip" description="Choose a payslip to inspect metadata and download it." align="center" />
        )
      }
    />
  );
}
