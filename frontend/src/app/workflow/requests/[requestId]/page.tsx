"use client";

import * as React from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/lib/auth";
import { parseUuidParam } from "@/lib/guards";
import { toastApiError } from "@/lib/toastApiError";
import type { UUID } from "@/lib/types";
import { approveRequest, cancelRequest, getRequest, rejectRequest } from "@/features/workflow/api/workflow";
import { workflowKeys } from "@/features/workflow/queryKeys";
import { WorkflowRequestContextPanel } from "@/features/workflow/components/WorkflowRequestContextPanel";
import { WorkflowRequestDetailCard } from "@/features/workflow/components/WorkflowRequestDetailCard";

import { DSCard } from "@/components/ds/DSCard";
import { EmptyState } from "@/components/ds/EmptyState";
import { ErrorState } from "@/components/ds/ErrorState";
import { PageHeader } from "@/components/ds/PageHeader";
import { WorkbenchTemplate } from "@/components/ds/templates/WorkbenchTemplate";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";

function hasAnyPermission(required: string[], granted: Set<string>): boolean {
  return required.some((p) => granted.has(p));
}

const REQUIRED = ["workflow:request:read", "workflow:request:admin"];
const REQUIRED_ACT = ["workflow:request:approve"];

export default function WorkflowRequestDeepLinkPage({
  params,
}: {
  params: { requestId?: string };
}) {
  const user = useAuth((s) => s.user);
  const permissions = useAuth((s) => s.permissions);
  const granted = React.useMemo(() => new Set(permissions ?? []), [permissions]);
  const canView = hasAnyPermission(REQUIRED, granted);
  const canAct = hasAnyPermission(REQUIRED_ACT, granted);
  const canReadFiles = granted.has("dms:file:read");
  const canWriteFiles = granted.has("dms:file:write");

  const qc = useQueryClient();

  const routeParams = useParams() as { requestId?: string | string[] };
  const requestIdRaw =
    (Array.isArray(routeParams.requestId) ? routeParams.requestId[0] : routeParams.requestId) ??
    params?.requestId ??
    null;
  const requestId = parseUuidParam(requestIdRaw) as UUID | null;

  const canFetch = Boolean(user && canView && requestId);

  const requestQ = useQuery({
    queryKey: workflowKeys.request(requestId),
    enabled: canFetch,
    queryFn: () => getRequest(requestId as UUID),
  });

  const approveM = useMutation({
    mutationFn: async () => approveRequest(requestId as UUID, { comment: null }),
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["workflow", "inbox"] }),
        qc.invalidateQueries({ queryKey: ["workflow", "outbox"] }),
        qc.invalidateQueries({ queryKey: workflowKeys.request(requestId) }),
      ]);
      await requestQ.refetch();
    },
    onError: (err) => toastApiError(err),
  });

  const [rejectOpen, setRejectOpen] = React.useState(false);
  const [rejectComment, setRejectComment] = React.useState("");

  const rejectM = useMutation({
    mutationFn: async () => rejectRequest(requestId as UUID, { comment: rejectComment.trim() }),
    onSuccess: async () => {
      setRejectOpen(false);
      setRejectComment("");
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["workflow", "inbox"] }),
        qc.invalidateQueries({ queryKey: ["workflow", "outbox"] }),
        qc.invalidateQueries({ queryKey: workflowKeys.request(requestId) }),
      ]);
      await requestQ.refetch();
    },
    onError: (err) => toastApiError(err),
  });

  const [cancelOpen, setCancelOpen] = React.useState(false);
  const cancelM = useMutation({
    mutationFn: async () => cancelRequest(requestId as UUID),
    onSuccess: async () => {
      setCancelOpen(false);
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["workflow", "inbox"] }),
        qc.invalidateQueries({ queryKey: ["workflow", "outbox"] }),
        qc.invalidateQueries({ queryKey: workflowKeys.request(requestId) }),
      ]);
      await requestQ.refetch();
    },
    onError: (err) => toastApiError(err),
  });

  const canCancel =
    granted.has("workflow:request:admin") ||
    (requestQ.data?.request.created_by_user_id != null &&
      user?.id &&
      requestQ.data.request.created_by_user_id === user.id);

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
        error={new Error("Your account does not have access to workflow requests.")}
      />
    );
  }

  if (!requestIdRaw) {
    return (
      <ErrorState
        title="Missing request id"
        error={new Error("Open a request from Inbox or Outbox.")}
        details={
          <div className="flex flex-wrap gap-2">
            <Button asChild variant="secondary">
              <Link href="/workflow/inbox">Go to inbox</Link>
            </Button>
            <Button asChild variant="outline">
              <Link href="/workflow/outbox">Go to outbox</Link>
            </Button>
          </div>
        }
      />
    );
  }

  if (!requestId) {
    return (
      <ErrorState
        title="Invalid request id"
        error={new Error(`Got: ${String(requestIdRaw)}`)}
        details={
          <Button asChild variant="outline">
            <Link href="/workflow/inbox">Back to inbox</Link>
          </Button>
        }
      />
    );
  }

  return (
    <WorkbenchTemplate
      header={<PageHeader title="Request" subtitle={`Request ${requestId}`} />}
      list={
        <DSCard surface="panel" className="p-[var(--ds-space-16)]">
          <div className="text-sm font-medium text-text-1">Navigation</div>
          <div className="mt-3 flex flex-col gap-2">
            <Button asChild variant="secondary">
              <Link href="/workflow/inbox">Inbox</Link>
            </Button>
            <Button asChild variant="outline">
              <Link href="/workflow/outbox">Outbox</Link>
            </Button>
          </div>
        </DSCard>
      }
      detail={
        <DSCard surface="card" className="p-[var(--ds-space-20)]">
          {requestQ.isLoading ? (
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
                  {requestQ.data.request.status !== "PENDING" ? (
                    <div className="text-sm text-text-3">
                      This request is not pending. Actions are disabled.
                    </div>
                  ) : canAct ? (
                    <div className="flex flex-wrap items-center gap-2">
                      <Button
                        type="button"
                        disabled={approveM.isPending}
                        onClick={() => approveM.mutate()}
                      >
                        {approveM.isPending ? "Approving..." : "Approve"}
                      </Button>
                      <Button
                        type="button"
                        variant="secondary"
                        disabled={rejectM.isPending}
                        onClick={() => setRejectOpen(true)}
                      >
                        Reject
                      </Button>
                      {canCancel ? (
                        <Button
                          type="button"
                          variant="outline"
                          disabled={cancelM.isPending}
                          onClick={() => setCancelOpen(true)}
                        >
                          Cancel request
                        </Button>
                      ) : null}
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
                        <Label htmlFor="wf-reject-comment-deeplink" className="text-xs text-text-2">
                          Comment (required)
                        </Label>
                        <textarea
                          id="wf-reject-comment-deeplink"
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

                  {cancelOpen ? (
                    <div className="space-y-3 rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-[var(--ds-space-16)]">
                      <div className="text-sm font-medium text-text-1">Cancel request</div>
                      <div className="text-sm text-text-2">
                        This will cancel the request if it is still pending.
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        <Button
                          type="button"
                          variant="outline"
                          className="border-danger/30 text-danger hover:bg-danger/10"
                          disabled={cancelM.isPending}
                          onClick={() => cancelM.mutate()}
                        >
                          {cancelM.isPending ? "Canceling..." : "Confirm cancel"}
                        </Button>
                        <Button type="button" variant="outline" onClick={() => setCancelOpen(false)}>
                          Close
                        </Button>
                      </div>
                    </div>
                  ) : null}
                </div>
              }
            />
          ) : (
            <EmptyState title="No data" description="Request not found." align="center" />
          )}
        </DSCard>
      }
      context={
        requestQ.data ? (
          <WorkflowRequestContextPanel
            requestId={requestId}
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
