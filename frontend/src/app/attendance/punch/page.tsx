"use client";

import * as React from "react";
import Link from "next/link";
import { toast } from "sonner";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/lib/auth";
import { toastApiError } from "@/lib/toastApiError";
import { getPunchState, punchIn, punchOut } from "@/features/attendance/api/attendance";
import { attendanceKeys } from "@/features/attendance/queryKeys";

import { DSCard } from "@/components/ds/DSCard";
import { ErrorState } from "@/components/ds/ErrorState";
import { PageHeader } from "@/components/ds/PageHeader";
import { StatusChip } from "@/components/ds/StatusChip";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

function hasPerm(perms: Set<string>, code: string): boolean {
  return perms.has(code);
}

function newIdempotencyKey(prefix: string): string {
  const rand =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (crypto as any).randomUUID()
      : `${Math.random().toString(16).slice(2)}-${Date.now()}`;
  return `${prefix}:${rand}`;
}

function formatMinutes(min: number): string {
  const m = Math.max(0, Number(min) || 0);
  const hh = Math.floor(m / 60);
  const mm = m % 60;
  return `${hh}h ${String(mm).padStart(2, "0")}m`;
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

export default function AttendancePunchPage() {
  const user = useAuth((s) => s.user);
  const permissions = useAuth((s) => s.permissions);
  const permSet = React.useMemo(() => new Set(permissions ?? []), [permissions]);

  const canRead = hasPerm(permSet, "attendance:punch:read");
  const canSubmit = hasPerm(permSet, "attendance:punch:submit");

  const qc = useQueryClient();

  const stateQ = useQuery({
    queryKey: attendanceKeys.punchState(),
    enabled: Boolean(user && canRead),
    queryFn: () => getPunchState(),
  });

  const punchInM = useMutation({
    mutationFn: async () => punchIn({ idempotency_key: newIdempotencyKey("punch-in") }),
    onSuccess: async () => {
      toast.success("Punched in");
      await Promise.all([
        qc.invalidateQueries({ queryKey: attendanceKeys.punchState() }),
        // Best-effort: refresh any visible month view.
        qc.invalidateQueries({ queryKey: ["attendance", "days"] }),
      ]);
    },
    onError: (err) => toastApiError(err),
  });

  const punchOutM = useMutation({
    mutationFn: async () => punchOut({ idempotency_key: newIdempotencyKey("punch-out") }),
    onSuccess: async () => {
      toast.success("Punched out");
      await Promise.all([
        qc.invalidateQueries({ queryKey: attendanceKeys.punchState() }),
        qc.invalidateQueries({ queryKey: ["attendance", "days"] }),
      ]);
    },
    onError: (err) => toastApiError(err),
  });

  if (!user) {
    return (
      <ErrorState
        title="Sign in required"
        error={new Error("Please sign in to view your punch state.")}
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
        error={new Error("Your account does not have access to punching.")}
      />
    );
  }

  const state = stateQ.data ?? null;
  const isPunchedIn = Boolean(state?.is_punched_in);
  const actionDisabled = !canSubmit || punchInM.isPending || punchOutM.isPending;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Punch"
        subtitle="Record your work sessions."
        actions={
          <Button asChild variant="secondary">
            <Link href="/attendance/days">View days</Link>
          </Button>
        }
      />

      <DSCard surface="card" className="p-[var(--ds-space-20)]">
        {stateQ.isLoading ? (
          <div className="space-y-4">
            <Skeleton className="h-6 w-56" />
            <Skeleton className="h-4 w-40" />
            <Skeleton className="h-10 w-32" />
          </div>
        ) : stateQ.error ? (
          <ErrorState title="Could not load punch state" error={stateQ.error} onRetry={stateQ.refetch} variant="inline" className="max-w-none" />
        ) : !state ? (
          <div className="text-sm text-text-2">No punch state available.</div>
        ) : (
          <div className="space-y-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="space-y-1">
                <div className="text-base font-semibold tracking-tight text-text-1">
                  {state.today_business_date}
                </div>
                <div className="text-sm text-text-2">
                  Effective status: <span className="font-medium">{state.effective_status_today}</span>
                </div>
              </div>
              <StatusChip status={isPunchedIn ? "IN" : "OUT"} />
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-4">
                <div className="text-xs font-medium text-text-2">Worked minutes (base)</div>
                <div className="mt-1 text-lg font-semibold text-text-1">
                  {formatMinutes(state.base_minutes_today)}
                </div>
              </div>
              <div className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-4">
                <div className="text-xs font-medium text-text-2">Worked minutes (effective)</div>
                <div className="mt-1 text-lg font-semibold text-text-1">
                  {formatMinutes(state.effective_minutes_today)}
                </div>
              </div>
            </div>

            <div className="space-y-2 text-sm">
              <div>
                <span className="text-text-2">Open session</span>:{" "}
                {state.open_session_started_at ? formatDateTime(state.open_session_started_at) : "—"}
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              {isPunchedIn ? (
                <Button
                  type="button"
                  disabled={actionDisabled}
                  onClick={() => punchOutM.mutate()}
                >
                  Punch out
                </Button>
              ) : (
                <Button
                  type="button"
                  disabled={actionDisabled}
                  onClick={() => punchInM.mutate()}
                >
                  Punch in
                </Button>
              )}
              {!canSubmit ? (
                <div className="text-xs text-text-3">Requires attendance:punch:submit</div>
              ) : null}
            </div>
          </div>
        )}
      </DSCard>
    </div>
  );
}
