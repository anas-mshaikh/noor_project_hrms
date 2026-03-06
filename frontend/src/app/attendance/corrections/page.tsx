"use client";

import * as React from "react";
import Link from "next/link";
import { toast } from "sonner";
import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/lib/auth";
import { toastApiError } from "@/lib/toastApiError";
import type { AttendanceCorrectionOut, UUID } from "@/lib/types";
import { cancelMyCorrection, listMyCorrections } from "@/features/attendance/api/attendance";
import { attendanceKeys } from "@/features/attendance/queryKeys";

import { DataTable } from "@/components/ds/DataTable";
import { DSCard } from "@/components/ds/DSCard";
import { EmptyState } from "@/components/ds/EmptyState";
import { ErrorState } from "@/components/ds/ErrorState";
import { FilterBar } from "@/components/ds/FilterBar";
import { PageHeader } from "@/components/ds/PageHeader";
import { RightPanelStack } from "@/components/ds/RightPanelStack";
import { StatusChip } from "@/components/ds/StatusChip";
import { ListRightPanelTemplate } from "@/components/ds/templates/ListRightPanelTemplate";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Sheet, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

function formatDateTime(value: string): string {
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

export default function AttendanceCorrectionsPage() {
  const user = useAuth((s) => s.user);
  const permissions = useAuth((s) => s.permissions);
  const permSet = React.useMemo(() => new Set(permissions ?? []), [permissions]);

  const canRead = permSet.has("attendance:correction:read");
  const canSubmit = permSet.has("attendance:correction:submit");

  const qc = useQueryClient();

  const [status, setStatus] = React.useState<string>("");
  const limit = 50;

  const correctionsQ = useInfiniteQuery({
    queryKey: attendanceKeys.myCorrections({ status: status ? status : null, limit }),
    enabled: Boolean(user && canRead),
    queryFn: ({ pageParam }) =>
      listMyCorrections({
        status: status ? status : null,
        limit,
        cursor: (pageParam as string | null) ?? null,
      }),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  });

  const items = React.useMemo(
    () => correctionsQ.data?.pages.flatMap((p) => p.items ?? []) ?? [],
    [correctionsQ.data]
  ) as AttendanceCorrectionOut[];

  const [cancelTarget, setCancelTarget] = React.useState<AttendanceCorrectionOut | null>(null);

  const cancelM = useMutation({
    mutationFn: async (id: UUID) => cancelMyCorrection(id),
    onSuccess: async () => {
      setCancelTarget(null);
      toast.success("Correction canceled");
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["attendance", "my-corrections"] }),
        qc.invalidateQueries({ queryKey: ["attendance", "days"] }),
        qc.invalidateQueries({ queryKey: ["workflow", "outbox"] }),
      ]);
    },
    onError: (err) => toastApiError(err),
  });

  if (!user) {
    return (
      <ErrorState
        title="Sign in required"
        error={new Error("Please sign in to view your corrections.")}
        details={
          <Button asChild variant="secondary">
            <Link href="/login">Sign in</Link>
          </Button>
        }
      />
    );
  }

  if (!canRead) {
    return (
      <ErrorState
        title="Access denied"
        error={new Error("Your account does not have access to attendance corrections.")}
      />
    );
  }

  const selectClassName =
    "h-9 rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm " +
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2";

  return (
    <>
      <ListRightPanelTemplate
        header={
          <PageHeader
            title="My Corrections"
            subtitle="Submitted attendance corrections."
            actions={
              <div className="flex items-center gap-2">
                <Button asChild variant="secondary">
                  <Link href="/attendance/days">Days</Link>
                </Button>
                <Button asChild variant="outline">
                  <Link href="/attendance/punch">Punch</Link>
                </Button>
              </div>
            }
          />
        }
        main={
          <DataTable
            toolbar={
              <FilterBar
                search={{
                  value: "",
                  onChange: () => {},
                  placeholder: "Search is not available in v1.",
                  disabled: true,
                }}
                chips={
                  <div className="flex items-center gap-2">
                    <Label className="text-xs text-text-2">Status</Label>
                    <select
                      className={selectClassName}
                      value={status}
                      onChange={(e) => setStatus(e.target.value)}
                      disabled={correctionsQ.isLoading}
                    >
                      <option value="">All</option>
                      <option value="PENDING">Pending</option>
                      <option value="APPROVED">Approved</option>
                      <option value="REJECTED">Rejected</option>
                      <option value="CANCELED">Canceled</option>
                    </select>
                  </div>
                }
                rightActions={
                  correctionsQ.hasNextPage ? (
                    <Button
                      type="button"
                      variant="secondary"
                      disabled={correctionsQ.isFetchingNextPage}
                      onClick={() => void correctionsQ.fetchNextPage()}
                    >
                      {correctionsQ.isFetchingNextPage ? "Loading..." : "Load more"}
                    </Button>
                  ) : null
                }
                onClearAll={status ? () => setStatus("") : undefined}
                clearDisabled={correctionsQ.isLoading}
              />
            }
            isLoading={correctionsQ.isLoading}
            error={correctionsQ.error}
            onRetry={correctionsQ.refetch}
            isEmpty={!correctionsQ.isLoading && !correctionsQ.error && items.length === 0}
            emptyState={
              <EmptyState
                title="No corrections"
                description="Your submitted corrections will appear here."
                align="center"
              />
            }
            skeleton={{ rows: 7, cols: 6 }}
          >
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Day</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Workflow</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((c) => (
                  <TableRow key={c.id}>
                    <TableCell className="font-medium">{c.day}</TableCell>
                    <TableCell className="text-text-2">{c.correction_type}</TableCell>
                    <TableCell>
                      <StatusChip status={c.status} />
                    </TableCell>
                    <TableCell className="text-text-2">
                      {c.workflow_request_id ? (
                        <Link
                          href={`/workflow/requests/${c.workflow_request_id}`}
                          className="hover:underline"
                        >
                          View
                        </Link>
                      ) : (
                        "—"
                      )}
                    </TableCell>
                    <TableCell className="text-text-2">{formatDateTime(c.created_at)}</TableCell>
                    <TableCell className="text-right">
                      {c.status === "PENDING" ? (
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          disabled={!canSubmit || cancelM.isPending}
                          onClick={() => setCancelTarget(c)}
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
        }
        right={
          <RightPanelStack>
            <DSCard surface="panel" className="p-[var(--ds-space-16)]">
              <div className="text-sm font-medium text-text-1">About</div>
              <div className="mt-2 text-sm text-text-2">
                Corrections require approval and may take a few minutes to reflect in your Days view.
              </div>
            </DSCard>
          </RightPanelStack>
        }
      />

      <Sheet
        open={Boolean(cancelTarget)}
        onOpenChange={(o) => {
          if (!o) setCancelTarget(null);
        }}
      >
        <SheetContent className="border-border-subtle bg-surface-2 backdrop-blur-xl">
          <SheetHeader>
            <SheetTitle>Cancel correction</SheetTitle>
            <SheetDescription>Cancel a pending correction request.</SheetDescription>
          </SheetHeader>

          <div className="space-y-3 px-4 text-sm">
            <div>
              Day: <span className="font-medium">{cancelTarget?.day ?? "—"}</span>
            </div>
            <div className="text-text-2">
              This will cancel the workflow request and mark the correction as canceled.
            </div>
          </div>

          <SheetFooter>
            <Button
              type="button"
              variant="secondary"
              disabled={cancelM.isPending}
              onClick={() => setCancelTarget(null)}
            >
              Close
            </Button>
            <Button
              type="button"
              disabled={!cancelTarget || cancelM.isPending}
              onClick={() => {
                if (!cancelTarget) return;
                cancelM.mutate(cancelTarget.id);
              }}
            >
              {cancelM.isPending ? "Canceling..." : "Cancel correction"}
            </Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>
    </>
  );
}
