"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/lib/auth";
import { parseYmdLocal } from "@/lib/dateRange";
import { toastApiError } from "@/lib/toastApiError";
import type { AttendanceCorrectionOut, DmsFileOut } from "@/lib/types";
import { uploadFile } from "@/features/dms/api/files";
import { submitMyCorrection } from "@/features/attendance/api/attendance";
import { requestedOverrideForCorrectionType } from "@/features/attendance/correctionMapping";

import { DSCard } from "@/components/ds/DSCard";
import { ErrorState } from "@/components/ds/ErrorState";
import { PageHeader } from "@/components/ds/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

function newIdempotencyKey(prefix: string): string {
  const rand =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (crypto as any).randomUUID()
      : `${Math.random().toString(16).slice(2)}-${Date.now()}`;
  return `${prefix}:${rand}`;
}

export default function AttendanceCorrectionNewPage() {
  const router = useRouter();
  const sp = useSearchParams();

  const user = useAuth((s) => s.user);
  const permissions = useAuth((s) => s.permissions);
  const permSet = React.useMemo(() => new Set(permissions ?? []), [permissions]);

  const canSubmit = permSet.has("attendance:correction:submit");
  const canReadFiles = permSet.has("dms:file:read");
  const canWriteFiles = permSet.has("dms:file:write");
  const canUploadEvidence = canReadFiles && canWriteFiles;

  const qc = useQueryClient();

  const dayParam = sp.get("day") ?? "";
  const [day, setDay] = React.useState(() => (parseYmdLocal(dayParam) ? dayParam : ""));
  const [correctionType, setCorrectionType] = React.useState("MARK_PRESENT");
  const [reason, setReason] = React.useState("");

  const [uploaded, setUploaded] = React.useState<DmsFileOut[]>([]);
  const [file, setFile] = React.useState<File | null>(null);
  const fileInputRef = React.useRef<HTMLInputElement | null>(null);

  const uploadM = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error("Choose a file first.");
      const meta = await uploadFile(file);
      return meta;
    },
    onSuccess: (meta) => {
      setUploaded((prev) => [...prev, meta]);
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      toast.success("Evidence uploaded");
    },
    onError: (err) => toastApiError(err),
  });

  const [created, setCreated] = React.useState<AttendanceCorrectionOut | null>(null);

  const submitM = useMutation({
    mutationFn: async () => {
      const requested = requestedOverrideForCorrectionType(correctionType);
      return submitMyCorrection({
        day,
        correction_type: correctionType,
        requested_override_status: requested,
        reason: reason.trim() ? reason.trim() : null,
        evidence_file_ids: uploaded.map((u) => u.id),
        idempotency_key: newIdempotencyKey("attendance-correction"),
      });
    },
    onSuccess: async (out) => {
      setCreated(out);
      toast.success("Correction submitted");
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["attendance", "days"] }),
        qc.invalidateQueries({ queryKey: ["attendance", "my-corrections"] }),
        qc.invalidateQueries({ queryKey: ["workflow", "outbox"] }),
      ]);
    },
    onError: (err) => toastApiError(err),
  });

  if (!user) {
    return (
      <ErrorState
        title="Sign in required"
        error={new Error("Please sign in to submit an attendance correction.")}
        details={
          <Button asChild variant="secondary">
            <Link href="/login">Sign in</Link>
          </Button>
        }
      />
    );
  }

  if (!canSubmit) {
    return (
      <ErrorState
        title="Access denied"
        error={new Error("Your account does not have access to submit corrections.")}
      />
    );
  }

  const requestedOverride = requestedOverrideForCorrectionType(correctionType);
  const canSubmitForm = Boolean(day && correctionType && requestedOverride && reason.trim());

  return (
    <div className="space-y-6">
      <PageHeader
        title="Request correction"
        subtitle="Submit an attendance correction for approval."
        actions={
          <div className="flex items-center gap-2">
            <Button asChild variant="secondary">
              <Link href="/attendance/days">Back to days</Link>
            </Button>
            <Button asChild variant="outline">
              <Link href="/attendance/corrections">My corrections</Link>
            </Button>
          </div>
        }
      />

      <DSCard surface="card" className="p-[var(--ds-space-20)]">
        <div className="space-y-6">
          {created ? (
            <div className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-4">
              <div className="text-sm font-medium text-text-1">Submitted</div>
              <div className="mt-1 text-sm text-text-2">
                Status: <span className="font-medium">{created.status}</span>
              </div>
              {created.workflow_request_id ? (
                <div className="mt-3">
                  <Button asChild variant="secondary">
                    <Link href={`/workflow/requests/${created.workflow_request_id}`}>View request</Link>
                  </Button>
                </div>
              ) : null}
            </div>
          ) : null}

          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-1">
              <Label htmlFor="corr-day">Day</Label>
              <Input
                id="corr-day"
                type="date"
                value={day}
                onChange={(e) => setDay(e.target.value)}
                disabled={submitM.isPending}
              />
            </div>

            <div className="space-y-1">
              <Label htmlFor="corr-type">Correction type</Label>
              <select
                id="corr-type"
                className="h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm"
                value={correctionType}
                onChange={(e) => setCorrectionType(e.target.value)}
                disabled={submitM.isPending}
              >
                <option value="MISSED_PUNCH">Missed punch</option>
                <option value="MARK_PRESENT">Mark present</option>
                <option value="MARK_ABSENT">Mark absent</option>
                <option value="WFH">Work from home</option>
                <option value="ON_DUTY">On duty</option>
              </select>
              <div className="text-xs text-text-3">Requested status: {requestedOverride}</div>
            </div>
          </div>

          <div className="space-y-1">
            <Label htmlFor="corr-reason">Reason</Label>
            <textarea
              id="corr-reason"
              className={[
                "min-h-24 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
              ].join(" ")}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Why are you requesting this correction?"
              disabled={submitM.isPending}
            />
            <div className="text-xs text-text-3">Reason is required.</div>
          </div>

          <div className="space-y-3">
            <div className="text-sm font-medium text-text-1">Evidence (optional)</div>
            {!canUploadEvidence ? (
              <div className="text-sm text-text-3">
                Evidence upload requires <span className="font-mono text-xs">dms:file:read</span>{" "}
                and <span className="font-mono text-xs">dms:file:write</span>.
              </div>
            ) : (
              <div className="space-y-3">
                <div className="grid gap-3 md:grid-cols-2">
                  <div className="space-y-1">
                    <Label htmlFor="corr-evidence-file">File</Label>
                    <input
                      id="corr-evidence-file"
                      ref={fileInputRef}
                      type="file"
                      onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                      disabled={uploadM.isPending || submitM.isPending}
                    />
                  </div>
                  <div className="flex items-end">
                    <Button
                      type="button"
                      variant="secondary"
                      disabled={!file || uploadM.isPending || submitM.isPending}
                      onClick={() => uploadM.mutate()}
                    >
                      {uploadM.isPending ? "Uploading..." : "Upload evidence"}
                    </Button>
                  </div>
                </div>

                {uploaded.length ? (
                  <div className="space-y-2">
                    {uploaded.map((u) => (
                      <div
                        key={u.id}
                        className="flex items-center justify-between gap-3 rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 px-3 py-2 text-sm"
                      >
                        <div className="min-w-0">
                          <div className="truncate font-medium text-text-1">{u.original_filename}</div>
                          <div className="truncate text-xs text-text-3">{u.id}</div>
                        </div>
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          disabled={submitM.isPending}
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
                  <div className="text-sm text-text-3">No evidence uploaded.</div>
                )}
              </div>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              disabled={!canSubmitForm || submitM.isPending}
              onClick={() => submitM.mutate()}
            >
              {submitM.isPending ? "Submitting..." : "Submit"}
            </Button>
            <Button
              type="button"
              variant="outline"
              disabled={submitM.isPending}
              onClick={() => router.push("/attendance/days")}
            >
              Cancel
            </Button>
          </div>
        </div>
      </DSCard>
    </div>
  );
}
