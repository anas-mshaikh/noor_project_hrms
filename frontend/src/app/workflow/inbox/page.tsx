"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/lib/auth";
import { parseUuidParam } from "@/lib/guards";
import { toastApiError } from "@/lib/toastApiError";
import type { UUID, WorkflowRequestSummaryOut } from "@/lib/types";
import {
  approveRequest,
  getRequest,
  listInbox,
  rejectRequest,
} from "@/features/workflow/api/workflow";
import { workflowKeys } from "@/features/workflow/queryKeys";
import { WorkflowRequestContextPanel } from "@/features/workflow/components/WorkflowRequestContextPanel";
import { WorkflowRequestDetailCard } from "@/features/workflow/components/WorkflowRequestDetailCard";

import { DSCard } from "@/components/ds/DSCard";
import { FilterBar } from "@/components/ds/FilterBar";
import { EmptyState } from "@/components/ds/EmptyState";
import { ErrorState } from "@/components/ds/ErrorState";
import { PageHeader } from "@/components/ds/PageHeader";
import { StatusChip } from "@/components/ds/StatusChip";
import { WorkbenchTemplate } from "@/components/ds/templates/WorkbenchTemplate";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";

function hasAnyPermission(required: string[], granted: Set<string>): boolean {
  return required.some((p) => granted.has(p));
}

const REQUIRED_VIEW = ["workflow:request:read", "workflow:request:admin"];
const REQUIRED_ACT = ["workflow:request:approve"];

function formatDateTime(value: string): string {
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

function RequestRow({
  item,
  selected,
  onSelect,
}: {
  item: WorkflowRequestSummaryOut;
  selected: boolean;
  onSelect: (id: UUID) => void;
}) {
  return (
    <button
      type="button"
      className={[
        "flex w-full items-center gap-3 rounded-[var(--ds-radius-16)] border px-[var(--ds-space-16)] text-left",
        "border-border-subtle bg-surface-1 hover:bg-surface-2",
        selected ? "ring-2 ring-ring" : "",
      ].join(" ")}
      style={{ height: "var(--ds-row-h)" }}
      onClick={() => onSelect(item.id)}
    >
      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="truncate text-sm font-medium text-text-1">{item.request_type_code}</div>
            <div className="truncate text-xs text-text-3">
              {item.subject ? item.subject : `Request ${item.id.slice(0, 8)}…`}
            </div>
          </div>
          <StatusChip status={item.status} />
        </div>
        <div className="mt-2 text-xs text-text-3">{formatDateTime(item.created_at)}</div>
      </div>
    </button>
  );
}

export default function WorkflowInboxPage() {
  const user = useAuth((s) => s.user);
  const permissions = useAuth((s) => s.permissions);
  const granted = React.useMemo(() => new Set(permissions ?? []), [permissions]);
  const canView = hasAnyPermission(REQUIRED_VIEW, granted);
  const canAct = hasAnyPermission(REQUIRED_ACT, granted);
  const canReadFiles = granted.has("dms:file:read");
  const canWriteFiles = granted.has("dms:file:write");

  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const qc = useQueryClient();

  const [type, setType] = React.useState("");
  const [status, setStatus] = React.useState<"pending" | "submitted">("pending");
  const limit = 50;

  const selectedIdRaw = searchParams.get("id");
  const selectedIdFromUrl = parseUuidParam(selectedIdRaw) as UUID | null;
  const [selectedId, setSelectedId] = React.useState<UUID | null>(selectedIdFromUrl);

  // Keep internal selection in sync with URL changes (deep links, back/forward).
  React.useEffect(() => {
    setSelectedId(selectedIdFromUrl);
  }, [selectedIdFromUrl]);

  const updateSelectedId = React.useCallback(
    (id: UUID | null) => {
      setSelectedId(id);
      const next = new URLSearchParams(searchParams.toString());
      if (id) next.set("id", id);
      else next.delete("id");
      const qs = next.toString();
      router.push(qs ? `${pathname}?${qs}` : pathname);
    },
    [pathname, router, searchParams]
  );

  const inboxQ = useInfiniteQuery({
    queryKey: workflowKeys.inbox({
      status,
      type: type.trim() ? type.trim() : null,
      limit,
    }),
    enabled: Boolean(user && canView),
    queryFn: ({ pageParam }) =>
      listInbox({
        status,
        type: type.trim() ? type.trim() : null,
        limit,
        cursor: (pageParam as string | null) ?? null,
      }),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  });

  const items = React.useMemo(
    () => inboxQ.data?.pages.flatMap((p) => p.items ?? []) ?? [],
    [inboxQ.data]
  );

  const requestQ = useQuery({
    queryKey: workflowKeys.request(selectedId),
    enabled: Boolean(user && canView && selectedId),
    queryFn: () => getRequest(selectedId as UUID),
  });

  const approveM = useMutation({
    mutationFn: async () => approveRequest(selectedId as UUID, { comment: null }),
    onSuccess: async () => {
      const invalidations = [
        qc.invalidateQueries({ queryKey: ["workflow", "inbox"] }),
        qc.invalidateQueries({ queryKey: ["workflow", "outbox"] }),
        qc.invalidateQueries({ queryKey: ["workflow", "request"] }),
      ];
      if (requestQ.data?.request.entity_type === "dms.document") {
        invalidations.push(qc.invalidateQueries({ queryKey: ["dms"] }));
      } else if (requestQ.data?.request.entity_type === "payroll.payrun") {
        invalidations.push(qc.invalidateQueries({ queryKey: ["payroll"] }));
      }
      await Promise.all(invalidations);
      updateSelectedId(null);
    },
    onError: (err) => toastApiError(err),
  });

  const [rejectOpen, setRejectOpen] = React.useState(false);
  const [rejectComment, setRejectComment] = React.useState("");

  const rejectM = useMutation({
    mutationFn: async () =>
      rejectRequest(selectedId as UUID, { comment: rejectComment.trim() }),
    onSuccess: async () => {
      setRejectOpen(false);
      setRejectComment("");
      const invalidations = [
        qc.invalidateQueries({ queryKey: ["workflow", "inbox"] }),
        qc.invalidateQueries({ queryKey: ["workflow", "outbox"] }),
        qc.invalidateQueries({ queryKey: ["workflow", "request"] }),
      ];
      if (requestQ.data?.request.entity_type === "dms.document") {
        invalidations.push(qc.invalidateQueries({ queryKey: ["dms"] }));
      } else if (requestQ.data?.request.entity_type === "payroll.payrun") {
        invalidations.push(qc.invalidateQueries({ queryKey: ["payroll"] }));
      }
      await Promise.all(invalidations);
      updateSelectedId(null);
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
        error={new Error("Your account does not have access to the workflow inbox.")}
      />
    );
  }

  const selectClassName = [
    "h-9 rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm",
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
    "disabled:cursor-not-allowed disabled:opacity-50",
  ].join(" ");

  return (
    <WorkbenchTemplate
      header={<PageHeader title="Inbox" subtitle="Requests assigned to you." />}
      list={
        <>
          <FilterBar
            search={{
              value: type,
              onChange: (v) => setType(v),
              placeholder: "Filter by request type...",
              disabled: inboxQ.isLoading,
            }}
            chips={
              <div className="flex items-center gap-2">
                <Label className="text-xs text-text-2">Status</Label>
                <select
                  className={selectClassName}
                  value={status}
                  onChange={(e) => setStatus(e.target.value as "pending" | "submitted")}
                >
                  <option value="pending">Pending</option>
                  <option value="submitted" disabled>
                    All (v1 not supported)
                  </option>
                </select>
              </div>
            }
            rightActions={
              inboxQ.hasNextPage ? (
                <Button
                  type="button"
                  variant="secondary"
                  disabled={inboxQ.isFetchingNextPage}
                  onClick={() => void inboxQ.fetchNextPage()}
                >
                  {inboxQ.isFetchingNextPage ? "Loading..." : "Load more"}
                </Button>
              ) : null
            }
            onClearAll={
              type || status !== "pending"
                ? () => {
                    setType("");
                    setStatus("pending");
                  }
                : undefined
            }
            clearDisabled={inboxQ.isLoading}
          />

          <DSCard surface="panel" className="p-[var(--ds-space-16)]">
            <div className="text-sm font-medium text-text-1">Requests</div>

            {inboxQ.isLoading ? (
              <div className="mt-3 space-y-2">
                {Array.from({ length: 6 }).map((_, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-3 rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 px-[var(--ds-space-16)]"
                    style={{ height: "var(--ds-row-h)" }}
                  >
                    <div className="min-w-0 flex-1 space-y-2">
                      <Skeleton className="h-3 w-40" />
                      <Skeleton className="h-3 w-24" />
                    </div>
                  </div>
                ))}
              </div>
            ) : inboxQ.isError ? (
              <div className="mt-4">
                <ErrorState
                  title="Failed to load inbox"
                  error={inboxQ.error}
                  onRetry={() => void inboxQ.refetch()}
                  variant="inline"
                />
              </div>
            ) : items.length === 0 ? (
              <div className="mt-6">
                <EmptyState
                  title="No requests"
                  description="You're all caught up."
                  align="center"
                />
              </div>
            ) : (
              <div className="mt-3 space-y-2">
                    {items.map((it) => (
                      <RequestRow
                        key={it.id}
                        item={it as WorkflowRequestSummaryOut}
                        selected={Boolean(selectedId && it.id === selectedId)}
                        onSelect={(id) => updateSelectedId(id)}
                      />
                    ))}
                  </div>
                )}
          </DSCard>
        </>
      }
      detail={
        <DSCard surface="card" className="p-[var(--ds-space-20)]">
          {!selectedId ? (
            selectedIdRaw && !selectedIdFromUrl ? (
              <ErrorState
                title="Invalid request id"
                error={new Error(`Got: ${selectedIdRaw}`)}
                details={
                  <Button type="button" variant="outline" onClick={() => updateSelectedId(null)}>
                    Clear selection
                  </Button>
                }
                variant="inline"
              />
            ) : (
              <EmptyState
                title="No request selected"
                description="Select a request from the list to view details and take action."
                align="center"
              />
            )
          ) : requestQ.isLoading ? (
            <div className="space-y-3">
              <Skeleton className="h-6 w-64" />
              <Skeleton className="h-4 w-40" />
              <Skeleton className="h-24 w-full" />
            </div>
          ) : requestQ.isError ? (
            <ErrorState
              title="Failed to load request"
              error={requestQ.error}
              onRetry={() => void requestQ.refetch()}
              variant="inline"
            />
          ) : requestQ.data ? (
            <WorkflowRequestDetailCard
              detail={requestQ.data}
              actions={
                <div className="space-y-4">
                  {canAct ? (
                    <div className="flex flex-wrap items-center gap-2">
                      <Button
                        type="button"
                        disabled={!selectedId || approveM.isPending}
                        onClick={() => approveM.mutate()}
                      >
                        {approveM.isPending ? "Approving..." : "Approve"}
                      </Button>

                      <Button
                        type="button"
                        variant="secondary"
                        disabled={!selectedId}
                        onClick={() => setRejectOpen(true)}
                      >
                        Reject
                      </Button>
                    </div>
                  ) : (
                    <div className="text-sm text-text-3">
                      You can view this request, but you do not have approval permissions.
                    </div>
                  )}

                  {rejectOpen ? (
                    <div className="space-y-3 rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-[var(--ds-space-16)]">
                      <div className="text-sm font-medium text-text-1">Reject request</div>
                      <div className="space-y-1">
                        <Label htmlFor="wf-reject-comment" className="text-xs text-text-2">
                          Comment (required)
                        </Label>
                        <textarea
                          id="wf-reject-comment"
                          className={[
                            "min-h-24 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm",
                            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                          ].join(" ")}
                          value={rejectComment}
                          onChange={(e) => setRejectComment(e.target.value)}
                          placeholder="Add a reason for rejection..."
                        />
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        <Button
                          type="button"
                          variant="outline"
                          className="border-danger/30 text-danger hover:bg-danger/10"
                          disabled={!rejectComment.trim() || rejectM.isPending}
                          onClick={() => rejectM.mutate()}
                        >
                          {rejectM.isPending ? "Rejecting..." : "Confirm reject"}
                        </Button>
                        <Button type="button" variant="outline" onClick={() => setRejectOpen(false)}>
                          Cancel
                        </Button>
                      </div>
                    </div>
                  ) : null}
                </div>
              }
            />
          ) : null}
        </DSCard>
      }
      context={
        requestQ.data && selectedId ? (
          <WorkflowRequestContextPanel
            requestId={selectedId}
            detail={requestQ.data}
            canReadFiles={canReadFiles}
            canWriteFiles={canWriteFiles}
          />
        ) : (
          <DSCard surface="panel" className="p-[var(--ds-space-16)]">
            <div className="text-sm font-medium text-text-1">Context</div>
            <div className="mt-3 text-sm text-text-2">
              Audit events, attachments, and comments will appear here.
            </div>
          </DSCard>
        )
      }
    />
  );
}
