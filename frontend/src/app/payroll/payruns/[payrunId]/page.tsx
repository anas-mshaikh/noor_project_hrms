"use client";

import * as React from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { toast } from "sonner";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { saveBlobAsFile } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { parseUuidParam } from "@/lib/guards";
import { toastApiError } from "@/lib/toastApiError";
import type { PayrunDetailOut, UUID } from "@/lib/types";
import { exportPayrun } from "@/features/payroll/api/payroll";
import {
  usePayrun,
  usePayrunPublish,
  usePayrunSubmitApproval,
} from "@/features/payroll/hooks";
import { payrollKeys } from "@/features/payroll/queryKeys";
import { formatPayrollMoney } from "@/features/payroll/utils/format";
import { canPublishPayrun, canSubmitPayrun } from "@/features/payroll/utils/gates";
import { payrollStatusLabel, payrunAnomalyLabel } from "@/features/payroll/utils/status";
import { getRequest } from "@/features/workflow/api/workflow";
import { workflowKeys } from "@/features/workflow/queryKeys";
import { WorkflowRequestDetailCard } from "@/features/workflow/components/WorkflowRequestDetailCard";

import { AuditTimeline, type AuditTimelineItem } from "@/components/ds/AuditTimeline";
import { DataTable } from "@/components/ds/DataTable";
import { DSCard } from "@/components/ds/DSCard";
import { EmptyState } from "@/components/ds/EmptyState";
import { ErrorState } from "@/components/ds/ErrorState";
import { PageHeader } from "@/components/ds/PageHeader";
import { RightPanelStack } from "@/components/ds/RightPanelStack";
import { StatusChip } from "@/components/ds/StatusChip";
import { ListRightPanelTemplate } from "@/components/ds/templates/ListRightPanelTemplate";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

function formatDateTime(value: string | null | undefined): string {
  if (!value) return "-";
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

function stableStringify(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function toneForEvent(eventType: string): AuditTimelineItem["tone"] {
  switch ((eventType ?? "").toUpperCase()) {
    case "APPROVED":
    case "REQUEST_APPROVED":
      return "success";
    case "REJECTED":
    case "REQUEST_REJECTED":
      return "danger";
    case "SUBMITTED":
    case "REQUEST_CREATED":
      return "info";
    default:
      return "neutral";
  }
}

function buildAuditItems(detail: PayrunDetailOut, workflowDetail?: Awaited<ReturnType<typeof getRequest>> | null): AuditTimelineItem[] {
  const items: AuditTimelineItem[] = [
    {
      title: "Payrun generated",
      time: formatDateTime(detail.payrun.generated_at),
      description: `Status ${payrollStatusLabel(detail.payrun.status)}`,
      tone: "info",
    },
  ];

  if (workflowDetail?.request) {
    items.push({
      title: "Approval request created",
      time: formatDateTime(workflowDetail.request.created_at),
      description: workflowDetail.request.id,
      tone: "info",
    });
    for (const event of workflowDetail.events ?? []) {
      items.push({
        title: event.event_type.replace(/_/g, " "),
        time: formatDateTime(event.created_at),
        description: event.actor_user_id ?? undefined,
        tone: toneForEvent(event.event_type),
      });
    }
  }

  if (detail.payrun.status === "PUBLISHED") {
    items.push({
      title: "Payrun published",
      time: formatDateTime(detail.payrun.updated_at),
      description: "Payslips were generated for included employees.",
      tone: "success",
    });
  }

  return items;
}

export default function PayrollPayrunDetailPage({
  params,
}: {
  params: { payrunId?: string };
}) {
  const permissions = useAuth((s) => s.permissions);
  const granted = React.useMemo(() => new Set(permissions ?? []), [permissions]);
  const canRead = granted.has("payroll:payrun:read");
  const canSubmit = granted.has("payroll:payrun:submit");
  const canPublish = granted.has("payroll:payrun:publish");
  const canExport = granted.has("payroll:payrun:export");
  const canReadWorkflow = granted.has("workflow:request:read") || granted.has("workflow:request:admin");

  const qc = useQueryClient();
  const routeParams = useParams() as { payrunId?: string | string[] };
  const payrunIdRaw =
    (Array.isArray(routeParams.payrunId) ? routeParams.payrunId[0] : routeParams.payrunId) ??
    params?.payrunId ??
    null;
  const payrunId = parseUuidParam(payrunIdRaw) as UUID | null;

  const [tab, setTab] = React.useState("employees");
  const [selectedItemId, setSelectedItemId] = React.useState<UUID | null>(null);

  const payrunQ = usePayrun(payrunId, true, Boolean(canRead && payrunId));
  const payrunDetail = payrunQ.data ?? null;

  React.useEffect(() => {
    if (!selectedItemId && payrunDetail?.items[0]) {
      setSelectedItemId(payrunDetail.items[0].id);
    }
  }, [payrunDetail, selectedItemId]);

  const workflowRequestId = payrunDetail?.payrun.workflow_request_id ?? null;
  const workflowQ = useQuery({
    queryKey: workflowKeys.request(workflowRequestId),
    enabled: Boolean(workflowRequestId && canReadWorkflow),
    queryFn: () => getRequest(workflowRequestId as UUID),
  });

  const selectedItem = React.useMemo(
    () => payrunDetail?.items.find((item) => item.id === selectedItemId) ?? payrunDetail?.items[0] ?? null,
    [payrunDetail, selectedItemId],
  );
  const selectedLines = React.useMemo(
    () => payrunDetail?.lines?.filter((line) => line.payrun_item_id === selectedItem?.id) ?? [],
    [payrunDetail, selectedItem],
  );
  const exceptions = React.useMemo(
    () =>
      payrunDetail?.items.filter(
        (item) => item.status === "EXCLUDED" || Boolean(item.anomalies_json),
      ) ?? [],
    [payrunDetail],
  );

  const submitM = usePayrunSubmitApproval(payrunId ?? ("" as UUID));
  const publishM = usePayrunPublish(payrunId ?? ("" as UUID));
  const exportM = useMutation({
    mutationFn: async () => {
      if (!payrunId) throw new Error("Missing payrun id.");
      return exportPayrun(payrunId);
    },
    onSuccess: (out) => {
      saveBlobAsFile(out.blob, out.filename);
      toast.success("Payroll export downloaded");
    },
    onError: (err) => toastApiError(err),
  });

  if (!canRead) {
    return (
      <ErrorState
        title="Access denied"
        error={new Error("Your account does not have access to payroll runs.")}
      />
    );
  }

  if (!payrunIdRaw) {
    return (
      <ErrorState
        title="Missing payrun id"
        error={new Error("Open a payrun from Payroll Payruns.")}
        details={
          <Button asChild variant="secondary">
            <Link href="/payroll/payruns">Back to payruns</Link>
          </Button>
        }
      />
    );
  }

  if (!payrunId) {
    return (
      <ErrorState
        title="Invalid payrun id"
        error={new Error(`Got: ${String(payrunIdRaw)}`)}
        details={
          <Button asChild variant="secondary">
            <Link href="/payroll/payruns">Back to payruns</Link>
          </Button>
        }
      />
    );
  }

  async function onSubmitApproval() {
    if (!payrunId) return;
    try {
      await submitM.mutateAsync();
      await Promise.all([
        qc.invalidateQueries({ queryKey: payrollKeys.payrun(payrunId, true) }),
        qc.invalidateQueries({ queryKey: ["workflow", "inbox"] }),
        qc.invalidateQueries({ queryKey: ["workflow", "outbox"] }),
      ]);
      toast.success("Payrun submitted for approval");
      await payrunQ.refetch();
    } catch (err) {
      toastApiError(err);
    }
  }

  async function onPublish() {
    if (!payrunId) return;
    try {
      const out = await publishM.mutateAsync();
      await Promise.all([
        qc.invalidateQueries({ queryKey: payrollKeys.payrun(payrunId, true) }),
        qc.invalidateQueries({ queryKey: ["payroll", "payslips", "me"] }),
      ]);
      toast.success(`Published ${out.published_count} payslip${out.published_count === 1 ? "" : "s"}`);
      await payrunQ.refetch();
    } catch (err) {
      toastApiError(err);
    }
  }

  const payrun = payrunDetail?.payrun ?? null;
  const totals = (payrun?.totals_json ?? null) as Record<string, unknown> | null;
  const currencyCode = typeof totals?.currency_code === "string" ? totals.currency_code : "SAR";
  const includedCount = Number(totals?.included_count ?? 0) || 0;
  const excludedCount = Number(totals?.excluded_count ?? 0) || 0;
  const grossTotal =
    typeof totals?.gross_total === "string" || typeof totals?.gross_total === "number"
      ? totals.gross_total
      : null;
  const deductionsTotal =
    typeof totals?.deductions_total === "string" ||
    typeof totals?.deductions_total === "number"
      ? totals.deductions_total
      : null;
  const netTotal =
    typeof totals?.net_total === "string" || typeof totals?.net_total === "number"
      ? totals.net_total
      : null;

  return (
    <ListRightPanelTemplate
      header={
        <PageHeader
          title={payrun ? `Payrun ${payrun.id.slice(0, 8)}…` : "Payrun"}
          subtitle={payrun ? `Status ${payrollStatusLabel(payrun.status)}` : `Payrun ${payrunId}`}
          actions={
            <div className="flex flex-wrap items-center gap-2">
              {canExport ? (
                <Button
                  type="button"
                  variant="secondary"
                  disabled={exportM.isPending || !payrun}
                  onClick={() => exportM.mutate()}
                >
                  {exportM.isPending ? "Exporting..." : "Export CSV"}
                </Button>
              ) : null}
              {canSubmit ? (
                <Button
                  type="button"
                  disabled={!canSubmitPayrun(payrun) || submitM.isPending}
                  onClick={() => void onSubmitApproval()}
                >
                  {submitM.isPending ? "Submitting..." : "Submit for approval"}
                </Button>
              ) : null}
              {canPublish ? (
                <Button
                  type="button"
                  variant="outline"
                  disabled={!canPublishPayrun(payrun) || publishM.isPending}
                  onClick={() => void onPublish()}
                >
                  {publishM.isPending ? "Publishing..." : "Publish"}
                </Button>
              ) : null}
              <Button asChild type="button" variant="outline">
                <Link href="/payroll/payruns">Back</Link>
              </Button>
            </div>
          }
        />
      }
      main={
        payrunQ.isLoading ? (
          <DSCard surface="card" className="p-[var(--ds-space-20)]">
            <div className="text-sm text-text-2">Loading payrun…</div>
          </DSCard>
        ) : payrunQ.error ? (
          <ErrorState
            title="Could not load payrun"
            error={payrunQ.error}
            onRetry={() => void payrunQ.refetch()}
          />
        ) : !payrunDetail ? (
          <EmptyState title="Payrun not found" description="This payrun does not exist or is not accessible." />
        ) : (
          <DSCard surface="card" className="p-[var(--ds-space-20)]">
            <Tabs value={tab} onValueChange={setTab}>
              <TabsList>
                <TabsTrigger value="employees">Employees</TabsTrigger>
                <TabsTrigger value="exceptions">Exceptions</TabsTrigger>
                <TabsTrigger value="audit">Audit</TabsTrigger>
              </TabsList>

              <TabsContent value="employees" className="mt-6">
                <DataTable
                  isLoading={false}
                  error={null}
                  onRetry={() => undefined}
                  isEmpty={payrunDetail.items.length === 0}
                  emptyState={<EmptyState title="No payrun items" description="Generate the payrun again after checking compensation and payables prerequisites." align="center" />}
                  skeleton={{ rows: 0, cols: 0 }}
                >
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Employee</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Payable days</TableHead>
                        <TableHead>Gross</TableHead>
                        <TableHead>Deductions</TableHead>
                        <TableHead>Net</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {payrunDetail.items.map((item) => (
                        <TableRow
                          key={item.id}
                          className="cursor-pointer"
                          onClick={() => setSelectedItemId(item.id)}
                        >
                          <TableCell className="font-medium">{item.employee_id}</TableCell>
                          <TableCell>
                            <StatusChip status={item.status} />
                          </TableCell>
                          <TableCell>{item.payable_days}</TableCell>
                          <TableCell>{formatPayrollMoney(item.gross_amount, currencyCode)}</TableCell>
                          <TableCell>{formatPayrollMoney(item.deductions_amount, currencyCode)}</TableCell>
                          <TableCell>{formatPayrollMoney(item.net_amount, currencyCode)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </DataTable>
              </TabsContent>

              <TabsContent value="exceptions" className="mt-6">
                <DataTable
                  isLoading={false}
                  error={null}
                  onRetry={() => undefined}
                  isEmpty={exceptions.length === 0}
                  emptyState={<EmptyState title="No exceptions" description="All included employees passed payroll input checks." align="center" />}
                  skeleton={{ rows: 0, cols: 0 }}
                >
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Employee</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Anomalies</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {exceptions.map((item) => {
                        const anomalyKeys = Object.keys(item.anomalies_json ?? {});
                        return (
                          <TableRow key={item.id}>
                            <TableCell className="font-medium">{item.employee_id}</TableCell>
                            <TableCell>
                              <StatusChip status={item.status} />
                            </TableCell>
                            <TableCell>
                              {anomalyKeys.length > 0 ? anomalyKeys.map(payrunAnomalyLabel).join(", ") : "Excluded from payrun"}
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </DataTable>
              </TabsContent>

              <TabsContent value="audit" className="mt-6">
                <AuditTimeline items={buildAuditItems(payrunDetail, workflowQ.data ?? null)} />
                {workflowQ.data ? (
                  <div className="mt-6 rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-4">
                    <WorkflowRequestDetailCard detail={workflowQ.data} />
                  </div>
                ) : null}
              </TabsContent>
            </Tabs>
          </DSCard>
        )
      }
      right={
        <RightPanelStack>
          <DSCard surface="panel" className="space-y-4 p-[var(--ds-space-16)]">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="text-sm font-semibold tracking-tight text-text-1">Payrun summary</div>
              {payrun ? <StatusChip status={payrun.status} /> : null}
            </div>
            {payrun ? (
              <div className="space-y-2 text-sm text-text-2">
                <div>Generated: {formatDateTime(payrun.generated_at)}</div>
                <div>Updated: {formatDateTime(payrun.updated_at)}</div>
                <div>Included employees: {includedCount}</div>
                <div>Excluded employees: {excludedCount}</div>
                <div>Gross total: {formatPayrollMoney(grossTotal, currencyCode)}</div>
                <div>Deductions total: {formatPayrollMoney(deductionsTotal, currencyCode)}</div>
                <div>Net total: {formatPayrollMoney(netTotal, currencyCode)}</div>
                <div>Computed at: {typeof totals?.computed_at === "string" ? formatDateTime(totals.computed_at) : "-"}</div>
                {payrun.workflow_request_id ? (
                  <Button asChild size="sm" type="button" variant="outline">
                    <Link href={`/workflow/requests/${payrun.workflow_request_id}`}>Open approval request</Link>
                  </Button>
                ) : null}
              </div>
            ) : null}
          </DSCard>

          <DSCard surface="panel" className="space-y-4 p-[var(--ds-space-16)]">
            <div className="text-sm font-semibold tracking-tight text-text-1">Selected employee</div>
            {selectedItem ? (
              <div className="space-y-2 text-sm text-text-2">
                <div className="font-medium text-text-1">{selectedItem.employee_id}</div>
                <div>Status: {selectedItem.status}</div>
                <div>Working days: {selectedItem.working_days_in_period}</div>
                <div>Payable minutes: {selectedItem.payable_minutes}</div>
                <div>Gross: {formatPayrollMoney(selectedItem.gross_amount, currencyCode)}</div>
                <div>Deductions: {formatPayrollMoney(selectedItem.deductions_amount, currencyCode)}</div>
                <div>Net: {formatPayrollMoney(selectedItem.net_amount, currencyCode)}</div>
                {selectedLines.length > 0 ? (
                  <div className="space-y-2 pt-2">
                    <div className="text-xs font-medium text-text-2">Line items</div>
                    {selectedLines.map((line) => (
                      <div key={line.id} className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-3">
                        <div className="text-sm font-medium text-text-1">{line.component_code}</div>
                        <div className="mt-1 text-xs text-text-3">{line.component_type}</div>
                        <div className="mt-1 text-sm text-text-2">{formatPayrollMoney(line.amount, currencyCode)}</div>
                      </div>
                    ))}
                  </div>
                ) : null}
                {selectedItem.anomalies_json ? (
                  <pre className="overflow-auto rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-3 text-xs text-text-2">
                    {stableStringify(selectedItem.anomalies_json)}
                  </pre>
                ) : null}
              </div>
            ) : (
              <EmptyState title="Select an employee" description="Choose a payrun item to inspect computed inputs and lines." align="center" />
            )}
          </DSCard>
        </RightPanelStack>
      }
    />
  );
}
