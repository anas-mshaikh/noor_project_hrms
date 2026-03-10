"use client";

import * as React from "react";
import Link from "next/link";
import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/lib/auth";
import { toastApiError } from "@/lib/toastApiError";
import type { UUID, WorkflowRequestSummaryOut } from "@/lib/types";
import { cancelRequest, listOutbox } from "@/features/workflow/api/workflow";
import { workflowKeys } from "@/features/workflow/queryKeys";
import { workflowStatusParam } from "@/features/workflow/status";
import { cn } from "@/lib/utils";

import { DataTable } from "@/components/ds/DataTable";
import { DSCard } from "@/components/ds/DSCard";
import { EmptyState } from "@/components/ds/EmptyState";
import { ErrorState } from "@/components/ds/ErrorState";
import { FilterBar } from "@/components/ds/FilterBar";
import { PageHeader } from "@/components/ds/PageHeader";
import { ListRightPanelTemplate } from "@/components/ds/templates/ListRightPanelTemplate";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { StatusChip } from "@/components/ds/StatusChip";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

function hasAnyPermission(required: string[], granted: Set<string>): boolean {
  return required.some((p) => granted.has(p));
}

const REQUIRED = ["workflow:request:read", "workflow:request:admin"];

function formatDateTime(value: string): string {
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

export default function WorkflowOutboxPage() {
  const user = useAuth((s) => s.user);
  const permissions = useAuth((s) => s.permissions);
  const granted = React.useMemo(() => new Set(permissions ?? []), [permissions]);
  const canView = hasAnyPermission(REQUIRED, granted);

  const qc = useQueryClient();

  const [type, setType] = React.useState("");
  const [status, setStatus] = React.useState<string>("");
  const limit = 50;

  const outboxQ = useInfiniteQuery({
    queryKey: workflowKeys.outbox({
      status: status ? workflowStatusParam(status) : null,
      type: type.trim() ? type.trim() : null,
      limit,
    }),
    enabled: Boolean(user && canView),
    queryFn: ({ pageParam }) =>
      listOutbox({
        status: status ? workflowStatusParam(status) : null,
        type: type.trim() ? type.trim() : null,
        limit,
        cursor: (pageParam as string | null) ?? null,
      }),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  });

  const items = React.useMemo(
    () => outboxQ.data?.pages.flatMap((p) => p.items ?? []) ?? [],
    [outboxQ.data]
  );

  const [cancelTarget, setCancelTarget] = React.useState<WorkflowRequestSummaryOut | null>(null);

  const cancelM = useMutation({
    mutationFn: async (id: UUID) => cancelRequest(id),
    onSuccess: async () => {
      const isDms = cancelTarget?.entity_type === "dms.document";
      setCancelTarget(null);
      const invalidations = [
        qc.invalidateQueries({ queryKey: ["workflow", "outbox"] }),
        qc.invalidateQueries({ queryKey: ["workflow", "inbox"] }),
        qc.invalidateQueries({ queryKey: ["workflow", "request"] }),
      ];
      if (isDms) {
        invalidations.push(qc.invalidateQueries({ queryKey: ["dms"] }));
      }
      await Promise.all(invalidations);
    },
    onError: (err) => toastApiError(err),
  });

  if (!user) {
    return (
      <ErrorState
        title="Sign in required"
        error={new Error("Please sign in to view workflow requests.")}
        details={
          <Button asChild variant="secondary">
            <Link href="/login">Sign in</Link>
          </Button>
        }
      />
    );
  }

  if (!canView) {
    return (
      <ErrorState
        title="Access denied"
        error={new Error("Your account does not have access to the workflow outbox.")}
      />
    );
  }

  const selectClassName = cn(
    "h-9 rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm",
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
    "disabled:cursor-not-allowed disabled:opacity-50"
  );

  return (
    <ListRightPanelTemplate
      header={<PageHeader title="Outbox" subtitle="Requests you created." />}
      main={
        <>
          <DataTable
            toolbar={
              <FilterBar
                search={{
                  value: type,
                  onChange: (v) => setType(v),
                  placeholder: "Filter by request type...",
                  disabled: outboxQ.isLoading,
                }}
                chips={
                  <div className="flex items-center gap-2">
                    <Label className="text-xs text-text-2">Status</Label>
                    <select
                      className={selectClassName}
                      value={status}
                      onChange={(e) => setStatus(e.target.value)}
                    >
                      <option value="">All</option>
                      <option value="PENDING">Pending</option>
                      <option value="APPROVED">Approved</option>
                      <option value="REJECTED">Rejected</option>
                      <option value="CANCELED">Canceled</option>
                      <option value="DRAFT">Draft</option>
                    </select>
                  </div>
                }
                rightActions={
                  outboxQ.hasNextPage ? (
                    <Button
                      type="button"
                      variant="secondary"
                      disabled={outboxQ.isFetchingNextPage}
                      onClick={() => void outboxQ.fetchNextPage()}
                    >
                      {outboxQ.isFetchingNextPage ? "Loading..." : "Load more"}
                    </Button>
                  ) : null
                }
                onClearAll={
                  type || status
                    ? () => {
                        setType("");
                        setStatus("");
                      }
                    : undefined
                }
                clearDisabled={outboxQ.isLoading}
              />
            }
            isLoading={outboxQ.isLoading}
            error={outboxQ.error}
            onRetry={outboxQ.refetch}
            isEmpty={!outboxQ.isLoading && !outboxQ.error && items.length === 0}
            emptyState={
              <EmptyState
                title="No requests"
                description="Your submitted requests will appear here."
                align="center"
              />
            }
            skeleton={{ rows: 7, cols: 5 }}
          >
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Type</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Subject</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell className="font-medium">
                      <Link href={`/workflow/requests/${r.id}`} className="hover:underline">
                        {r.request_type_code}
                      </Link>
                    </TableCell>
                    <TableCell>
                      <StatusChip status={r.status} />
                    </TableCell>
                    <TableCell className="text-text-2">{r.subject ?? "—"}</TableCell>
                    <TableCell className="text-text-2">{formatDateTime(r.created_at)}</TableCell>
                    <TableCell className="text-right">
                      {r.status === "PENDING" ? (
                        <Button
                          type="button"
                          variant="outline"
                          disabled={cancelM.isPending}
                          onClick={() => setCancelTarget(r)}
                        >
                          Cancel
                        </Button>
                      ) : (
                        <span className="text-xs text-text-3">—</span>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </DataTable>

          <Sheet
            open={Boolean(cancelTarget)}
            onOpenChange={(o) => {
              if (!o) setCancelTarget(null);
            }}
          >
            <SheetContent className="border-border-subtle bg-surface-2 backdrop-blur-xl">
              <SheetHeader>
                <SheetTitle>Cancel request</SheetTitle>
                <SheetDescription>
                  Cancel a pending request. This action cannot be undone.
                </SheetDescription>
              </SheetHeader>

              <div className="space-y-3 px-4 text-sm">
                <div className="space-y-1">
                  <div className="text-xs text-text-2">Request</div>
                  <div className="font-mono text-xs">{cancelTarget?.id}</div>
                </div>
                <div className="space-y-1">
                  <div className="text-xs text-text-2">Type</div>
                  <div>{cancelTarget?.request_type_code}</div>
                </div>
              </div>

              <SheetFooter>
                <Button
                  type="button"
                  variant="outline"
                  disabled={!cancelTarget || cancelM.isPending}
                  className="border-danger/30 text-danger hover:bg-danger/10"
                  onClick={() => cancelTarget && cancelM.mutate(cancelTarget.id)}
                >
                  {cancelM.isPending ? "Canceling..." : "Confirm cancel"}
                </Button>
              </SheetFooter>
            </SheetContent>
          </Sheet>
        </>
      }
      right={
        <DSCard surface="panel" className="p-[var(--ds-space-16)]">
          <div className="text-sm font-medium text-text-1">About outbox</div>
          <div className="mt-3 text-sm text-text-2">
            Track request status and cancel pending requests (when supported).
          </div>
        </DSCard>
      }
    />
  );
}
