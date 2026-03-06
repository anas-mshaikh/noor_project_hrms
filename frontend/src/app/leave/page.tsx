"use client";

import * as React from "react";
import Link from "next/link";
import { toast } from "sonner";
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/lib/auth";
import { useSelection } from "@/lib/selection";
import { toastApiError } from "@/lib/toastApiError";
import type { DmsFileOut, LeaveBalanceOut, LeaveRequestOut, UUID } from "@/lib/types";
import { uploadFile } from "@/features/dms/api/files";
import { cancelMyLeaveRequest, getMyBalances, listMyLeaveRequests, submitMyLeaveRequest } from "@/features/leave/api/leave";
import { leaveKeys } from "@/features/leave/queryKeys";

import { DataTable } from "@/components/ds/DataTable";
import { DSCard } from "@/components/ds/DSCard";
import { EmptyState } from "@/components/ds/EmptyState";
import { ErrorState } from "@/components/ds/ErrorState";
import { FilterBar } from "@/components/ds/FilterBar";
import { PageHeader } from "@/components/ds/PageHeader";
import { RightPanelStack } from "@/components/ds/RightPanelStack";
import { StatusChip } from "@/components/ds/StatusChip";
import { ListRightPanelTemplate } from "@/components/ds/templates/ListRightPanelTemplate";
import { StorePicker } from "@/components/StorePicker";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Sheet, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

function newIdempotencyKey(prefix: string): string {
  const rand =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (crypto as any).randomUUID()
      : `${Math.random().toString(16).slice(2)}-${Date.now()}`;
  return `${prefix}:${rand}`;
}

function formatDate(value: string): string {
  // Dates are already YYYY-MM-DD from backend; keep them stable.
  return value;
}

function formatDateTime(value: string): string {
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

export default function LeavePage() {
  const user = useAuth((s) => s.user);
  const permissions = useAuth((s) => s.permissions);
  const permSet = React.useMemo(() => new Set(permissions ?? []), [permissions]);

  const canReadBalances = permSet.has("leave:balance:read");
  const canReadRequests = permSet.has("leave:request:read");
  const canSubmit = permSet.has("leave:request:submit");

  const canReadFiles = permSet.has("dms:file:read");
  const canWriteFiles = permSet.has("dms:file:write");
  const canUploadAttachments = canReadFiles && canWriteFiles;

  const companyId = useSelection((s) => s.companyId);
  const branchId = useSelection((s) => s.branchId);
  const canSubmitInScope = Boolean(companyId && branchId);

  const qc = useQueryClient();

  const year = new Date().getFullYear();

  const balancesQ = useQuery({
    queryKey: leaveKeys.balances(year),
    enabled: Boolean(user && canReadBalances),
    queryFn: () => getMyBalances({ year }),
  });

  const balances = (balancesQ.data?.items ?? []) as LeaveBalanceOut[];

  const [status, setStatus] = React.useState<string>("");
  const limit = 50;

  const requestsQ = useInfiniteQuery({
    queryKey: leaveKeys.myRequests({ status: status ? status : null, limit }),
    enabled: Boolean(user && canReadRequests),
    queryFn: ({ pageParam }) =>
      listMyLeaveRequests({
        status: status ? status : null,
        limit,
        cursor: (pageParam as string | null) ?? null,
      }),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  });

  const requests = React.useMemo(
    () => requestsQ.data?.pages.flatMap((p) => p.items ?? []) ?? [],
    [requestsQ.data]
  ) as LeaveRequestOut[];

  const [selectedId, setSelectedId] = React.useState<string | null>(null);
  const selected = React.useMemo(
    () => (selectedId ? requests.find((r) => r.id === selectedId) ?? null : null),
    [requests, selectedId]
  );

  // ----- Apply sheet state -----
  const [applyOpen, setApplyOpen] = React.useState(false);
  const [leaveTypeCode, setLeaveTypeCode] = React.useState("");
  const [startDate, setStartDate] = React.useState("");
  const [endDate, setEndDate] = React.useState("");
  const [unit, setUnit] = React.useState<"DAY" | "HALF_DAY">("DAY");
  const [halfDayPart, setHalfDayPart] = React.useState<"AM" | "PM" | "">("");
  const [reason, setReason] = React.useState("");

  const [uploaded, setUploaded] = React.useState<DmsFileOut[]>([]);
  const [file, setFile] = React.useState<File | null>(null);
  const fileInputRef = React.useRef<HTMLInputElement | null>(null);

  const uploadM = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error("Choose a file first.");
      return uploadFile(file);
    },
    onSuccess: (meta) => {
      setUploaded((prev) => [...prev, meta]);
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      toast.success("Attachment uploaded");
    },
    onError: (err) => toastApiError(err),
  });

  const applyM = useMutation({
    mutationFn: async () =>
      submitMyLeaveRequest({
        leave_type_code: leaveTypeCode,
        start_date: startDate,
        end_date: endDate,
        unit,
        half_day_part: unit === "HALF_DAY" ? (halfDayPart || null) : null,
        reason: reason.trim() ? reason.trim() : null,
        attachment_file_ids: uploaded.map((u) => u.id),
        idempotency_key: newIdempotencyKey("leave"),
      }),
    onSuccess: async (out) => {
      toast.success("Leave request submitted");
      setApplyOpen(false);
      setSelectedId(out.id);
      // Reset form
      setReason("");
      setUploaded([]);
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["leave", "balances"] }),
        qc.invalidateQueries({ queryKey: ["leave", "my-requests"] }),
        qc.invalidateQueries({ queryKey: ["workflow", "outbox"] }),
      ]);
    },
    onError: (err) => toastApiError(err),
  });

  const [cancelTarget, setCancelTarget] = React.useState<LeaveRequestOut | null>(null);
  const cancelM = useMutation({
    mutationFn: async (id: UUID) => cancelMyLeaveRequest(id),
    onSuccess: async () => {
      setCancelTarget(null);
      toast.success("Leave request canceled");
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["leave", "balances"] }),
        qc.invalidateQueries({ queryKey: ["leave", "my-requests"] }),
        qc.invalidateQueries({ queryKey: ["workflow", "outbox"] }),
      ]);
    },
    onError: (err) => toastApiError(err),
  });

  if (!user) {
    return (
      <ErrorState
        title="Sign in required"
        error={new Error("Please sign in to view leave balances and requests.")}
        details={
          <Button asChild variant="secondary">
            <Link href="/login">Sign in</Link>
          </Button>
        }
      />
    );
  }

  if (!canReadBalances && !canReadRequests) {
    return (
      <ErrorState
        title="Access denied"
        error={new Error("Your account does not have access to leave.")}
      />
    );
  }

  const applyDisabledReason = !canSubmit
    ? "Requires leave:request:submit"
    : !canSubmitInScope
      ? "Select company + branch scope to apply leave"
      : balances.length === 0
        ? "No leave types configured"
        : null;

  const selectClassName =
    "h-9 rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm " +
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2";

  return (
    <>
      <ListRightPanelTemplate
        header={
          <PageHeader
            title="Leave"
            subtitle="Balances and requests."
            actions={
              <div className="flex items-center gap-2">
                <Sheet open={applyOpen} onOpenChange={setApplyOpen}>
                  <SheetTrigger asChild>
                    <Button type="button" disabled={Boolean(applyDisabledReason)}>
                      Apply leave
                    </Button>
                  </SheetTrigger>
                  <SheetContent className="border-border-subtle bg-surface-2 backdrop-blur-xl">
                    <SheetHeader>
                      <SheetTitle>Apply leave</SheetTitle>
                      <SheetDescription>Submit a leave request for approval.</SheetDescription>
                    </SheetHeader>

                    <div className="space-y-4 px-4 text-sm">
                      {applyDisabledReason ? (
                        <div className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-3 text-text-2">
                          {applyDisabledReason}
                        </div>
                      ) : null}

                      <div className="space-y-1">
                        <Label htmlFor="leave-type">Leave type</Label>
                        <select
                          id="leave-type"
                          className="h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm"
                          value={leaveTypeCode}
                          onChange={(e) => setLeaveTypeCode(e.target.value)}
                          disabled={applyM.isPending}
                        >
                          <option value="">Select…</option>
                          {balances.map((b) => (
                            <option key={b.leave_type_code} value={b.leave_type_code}>
                              {b.leave_type_code} — {b.leave_type_name}
                            </option>
                          ))}
                        </select>
                      </div>

                      <div className="grid gap-3 md:grid-cols-2">
                        <div className="space-y-1">
                          <Label htmlFor="leave-start">Start</Label>
                          <Input
                            id="leave-start"
                            type="date"
                            value={startDate}
                            onChange={(e) => setStartDate(e.target.value)}
                            disabled={applyM.isPending}
                          />
                        </div>
                        <div className="space-y-1">
                          <Label htmlFor="leave-end">End</Label>
                          <Input
                            id="leave-end"
                            type="date"
                            value={endDate}
                            onChange={(e) => setEndDate(e.target.value)}
                            disabled={applyM.isPending}
                          />
                        </div>
                      </div>

                      <div className="grid gap-3 md:grid-cols-2">
                        <div className="space-y-1">
                          <Label htmlFor="leave-unit">Unit</Label>
                          <select
                            id="leave-unit"
                            className="h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm"
                            value={unit}
                            onChange={(e) => setUnit(e.target.value as "DAY" | "HALF_DAY")}
                            disabled={applyM.isPending}
                          >
                            <option value="DAY">Full day</option>
                            <option value="HALF_DAY">Half day</option>
                          </select>
                        </div>
                        <div className="space-y-1">
                          <Label htmlFor="leave-half">Half-day part</Label>
                          <select
                            id="leave-half"
                            className="h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm"
                            value={halfDayPart}
                            onChange={(e) => setHalfDayPart(e.target.value as "AM" | "PM" | "")}
                            disabled={applyM.isPending || unit !== "HALF_DAY"}
                          >
                            <option value="">—</option>
                            <option value="AM">AM</option>
                            <option value="PM">PM</option>
                          </select>
                        </div>
                      </div>

                      <div className="space-y-1">
                        <Label htmlFor="leave-reason">Reason (optional)</Label>
                        <textarea
                          id="leave-reason"
                          className={[
                            "min-h-24 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm",
                            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                          ].join(" ")}
                          value={reason}
                          onChange={(e) => setReason(e.target.value)}
                          placeholder="Reason for leave..."
                          disabled={applyM.isPending}
                        />
                      </div>

                      <div className="space-y-3">
                        <div className="text-sm font-medium text-text-1">Attachments (optional)</div>
                        {!canUploadAttachments ? (
                          <div className="text-sm text-text-3">
                            Upload requires <span className="font-mono text-xs">dms:file:read</span>{" "}
                            and <span className="font-mono text-xs">dms:file:write</span>.
                          </div>
                        ) : (
                          <div className="space-y-2">
                            <div className="space-y-1">
                              <Label htmlFor="leave-attachment">File</Label>
                              <input
                                id="leave-attachment"
                                ref={fileInputRef}
                                type="file"
                                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                                disabled={applyM.isPending || uploadM.isPending}
                              />
                            </div>
                            <Button
                              type="button"
                              variant="secondary"
                              disabled={!file || applyM.isPending || uploadM.isPending}
                              onClick={() => uploadM.mutate()}
                            >
                              {uploadM.isPending ? "Uploading..." : "Upload attachment"}
                            </Button>
                            {uploaded.length ? (
                              <div className="space-y-2">
                                {uploaded.map((u) => (
                                  <div
                                    key={u.id}
                                    className="flex items-center justify-between gap-3 rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 px-3 py-2"
                                  >
                                    <div className="min-w-0">
                                      <div className="truncate text-sm font-medium text-text-1">{u.original_filename}</div>
                                      <div className="truncate text-xs text-text-3">{u.id}</div>
                                    </div>
                                    <Button
                                      type="button"
                                      size="sm"
                                      variant="outline"
                                      disabled={applyM.isPending}
                                      onClick={() =>
                                        setUploaded((prev) => prev.filter((x) => x.id !== u.id))
                                      }
                                    >
                                      Remove
                                    </Button>
                                  </div>
                                ))}
                              </div>
                            ) : (
                              <div className="text-sm text-text-3">No attachments uploaded.</div>
                            )}
                          </div>
                        )}
                      </div>
                    </div>

                    <SheetFooter>
                      <Button
                        type="button"
                        variant="secondary"
                        disabled={applyM.isPending}
                        onClick={() => setApplyOpen(false)}
                      >
                        Close
                      </Button>
                      <Button
                        type="button"
                        disabled={
                          Boolean(applyDisabledReason) ||
                          !leaveTypeCode ||
                          !startDate ||
                          !endDate ||
                          (unit === "HALF_DAY" && (!halfDayPart || startDate !== endDate)) ||
                          applyM.isPending
                        }
                        onClick={() => applyM.mutate()}
                      >
                        {applyM.isPending ? "Submitting..." : "Submit request"}
                      </Button>
                    </SheetFooter>
                  </SheetContent>
                </Sheet>
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
                      disabled={requestsQ.isLoading}
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
                  requestsQ.hasNextPage ? (
                    <Button
                      type="button"
                      variant="secondary"
                      disabled={requestsQ.isFetchingNextPage}
                      onClick={() => void requestsQ.fetchNextPage()}
                    >
                      {requestsQ.isFetchingNextPage ? "Loading..." : "Load more"}
                    </Button>
                  ) : null
                }
                onClearAll={status ? () => setStatus("") : undefined}
                clearDisabled={requestsQ.isLoading}
              />
            }
            isLoading={requestsQ.isLoading}
            error={requestsQ.error}
            onRetry={requestsQ.refetch}
            isEmpty={!requestsQ.isLoading && !requestsQ.error && requests.length === 0}
            emptyState={
              <EmptyState
                title="No leave requests"
                description="Your submitted leave requests will appear here."
                align="center"
              />
            }
            skeleton={{ rows: 7, cols: 6 }}
          >
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Type</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Start</TableHead>
                  <TableHead>End</TableHead>
                  <TableHead>Days</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {requests.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell className="font-medium">
                      <button
                        type="button"
                        className="hover:underline"
                        onClick={() => setSelectedId(r.id)}
                      >
                        {r.leave_type_code}
                      </button>
                    </TableCell>
                    <TableCell>
                      <StatusChip status={r.status} />
                    </TableCell>
                    <TableCell className="text-text-2">{formatDate(r.start_date)}</TableCell>
                    <TableCell className="text-text-2">{formatDate(r.end_date)}</TableCell>
                    <TableCell className="text-text-2">{r.requested_days}</TableCell>
                    <TableCell className="text-right">
                      {r.workflow_request_id ? (
                        <Button asChild size="sm" variant="outline">
                          <Link href={`/workflow/requests/${r.workflow_request_id}`}>View</Link>
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
              <div className="text-sm font-medium text-text-1">Balances ({year})</div>
              {balancesQ.isLoading ? (
                <div className="mt-3 text-sm text-text-3">Loading…</div>
              ) : balancesQ.error ? (
                <ErrorState
                  title="Could not load balances"
                  error={balancesQ.error}
                  onRetry={balancesQ.refetch}
                  variant="inline"
                  className="max-w-none"
                />
              ) : balances.length === 0 ? (
                <div className="mt-3 text-sm text-text-3">No leave types configured.</div>
              ) : (
                <div className="mt-3 space-y-2">
                  {balances.map((b) => (
                    <div
                      key={b.leave_type_code}
                      className="flex items-center justify-between gap-3 rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 px-3 py-2 text-sm"
                    >
                      <div className="min-w-0">
                        <div className="truncate font-medium text-text-1">{b.leave_type_code}</div>
                        <div className="truncate text-xs text-text-3">{b.leave_type_name}</div>
                      </div>
                      <div className="text-right">
                        <div className="font-medium text-text-1">{b.balance_days}</div>
                        <div className="text-xs text-text-3">pending {b.pending_days}</div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </DSCard>

            {!canSubmitInScope ? (
              <DSCard surface="panel" className="p-[var(--ds-space-16)]">
                <div className="text-sm font-medium text-text-1">Scope required</div>
                <div className="mt-1 text-sm text-text-2">
                  Select a company and branch to apply leave.
                </div>
                <div className="mt-3">
                  <StorePicker />
                </div>
              </DSCard>
            ) : null}

            {selected ? (
              <DSCard surface="panel" className="p-[var(--ds-space-16)]">
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-1">
                    <div className="text-sm font-medium text-text-1">{selected.leave_type_code}</div>
                    <div className="text-xs text-text-3">{formatDateTime(selected.created_at)}</div>
                  </div>
                  <StatusChip status={selected.status} />
                </div>

                <div className="mt-4 space-y-2 text-sm">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-text-2">Start</div>
                    <div className="font-medium text-text-1">{formatDate(selected.start_date)}</div>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-text-2">End</div>
                    <div className="font-medium text-text-1">{formatDate(selected.end_date)}</div>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-text-2">Days</div>
                    <div className="font-medium text-text-1">{selected.requested_days}</div>
                  </div>
                </div>

                <div className="mt-4 flex flex-wrap items-center gap-2">
                  {selected.workflow_request_id ? (
                    <Button asChild variant="secondary">
                      <Link href={`/workflow/requests/${selected.workflow_request_id}`}>View workflow</Link>
                    </Button>
                  ) : null}
                  {selected.status === "PENDING" ? (
                    <Button
                      type="button"
                      variant="outline"
                      disabled={!canSubmit || cancelM.isPending}
                      onClick={() => setCancelTarget(selected)}
                    >
                      Cancel request
                    </Button>
                  ) : null}
                </div>
              </DSCard>
            ) : (
              <DSCard surface="panel" className="p-[var(--ds-space-16)]">
                <EmptyState
                  title="Select a request"
                  description="Pick a request to see details."
                  align="center"
                />
              </DSCard>
            )}
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
            <SheetTitle>Cancel leave request</SheetTitle>
            <SheetDescription>Cancel a pending leave request.</SheetDescription>
          </SheetHeader>

          <div className="space-y-3 px-4 text-sm">
            <div>
              Type: <span className="font-medium">{cancelTarget?.leave_type_code ?? "—"}</span>
            </div>
            <div className="text-text-2">
              This will cancel the workflow request and mark the leave request as canceled.
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
              {cancelM.isPending ? "Canceling..." : "Cancel request"}
            </Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>
    </>
  );
}
