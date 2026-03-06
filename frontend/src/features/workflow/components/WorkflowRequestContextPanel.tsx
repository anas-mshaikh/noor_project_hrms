"use client";

import * as React from "react";
import { useMutation, useQueries, useQueryClient } from "@tanstack/react-query";

import { saveBlobAsFile } from "@/lib/api";
import { toastApiError } from "@/lib/toastApiError";
import type { UUID, WorkflowRequestDetailOut } from "@/lib/types";
import {
  uploadFile,
  getFileMeta,
  downloadFile,
} from "@/features/dms/api/files";
import { dmsKeys } from "@/features/dms/queryKeys";
import { addAttachment, addComment } from "@/features/workflow/api/workflow";
import { workflowKeys } from "@/features/workflow/queryKeys";

import {
  AuditTimeline,
  type AuditTimelineItem,
} from "@/components/ds/AuditTimeline";
import { DSCard } from "@/components/ds/DSCard";
import { RightPanelStack } from "@/components/ds/RightPanelStack";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

function formatDateTime(value: string): string {
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

function eventTitle(type: string): string {
  switch (String(type).toUpperCase()) {
    case "REQUEST_APPROVED":
      return "Approved";
    case "REQUEST_REJECTED":
      return "Rejected";
    case "REQUEST_CANCELED":
    case "REQUEST_CANCELLED":
      return "Canceled";
    case "COMMENT_ADDED":
      return "Comment";
    case "ATTACHMENT_ADDED":
      return "Attachment";
    default:
      return type;
  }
}

function timelineItems(detail: WorkflowRequestDetailOut): AuditTimelineItem[] {
  const items: AuditTimelineItem[] = (detail.events ?? []).map((e) => ({
    title: eventTitle(e.event_type),
    time: formatDateTime(e.created_at),
    description: e.correlation_id ? `ref ${e.correlation_id}` : undefined,
    tone:
      e.event_type === "REQUEST_APPROVED"
        ? "success"
        : e.event_type === "REQUEST_REJECTED"
          ? "danger"
          : e.event_type === "REQUEST_CANCELED"
            ? "neutral"
            : "neutral",
  }));
  return items.length > 0
    ? items
    : [{ title: "No activity yet", tone: "neutral" }];
}

export function WorkflowRequestContextPanel({
  requestId,
  detail,
  canReadFiles,
  canWriteFiles,
}: {
  requestId: UUID;
  detail: WorkflowRequestDetailOut;
  canReadFiles: boolean;
  canWriteFiles: boolean;
}) {
  const qc = useQueryClient();

  const [comment, setComment] = React.useState("");

  const addCommentM = useMutation({
    mutationFn: async () => addComment(requestId, { body: comment.trim() }),
    onSuccess: async () => {
      setComment("");
      await qc.invalidateQueries({ queryKey: workflowKeys.request(requestId) });
    },
    onError: (err) => toastApiError(err),
  });

  const attachments = detail.attachments ?? [];

  const fileMetaQs = useQueries({
    queries: attachments.map((a) => ({
      queryKey: dmsKeys.fileMeta(a.file_id),
      enabled: canReadFiles,
      queryFn: () => getFileMeta(a.file_id),
    })),
  });

  const fileMetaById = React.useMemo(() => {
    const m = new Map<
      string,
      { original_filename: string; content_type: string }
    >();
    for (const q of fileMetaQs) {
      if (q.data) {
        m.set(q.data.id, {
          original_filename: q.data.original_filename,
          content_type: q.data.content_type,
        });
      }
    }
    return m;
  }, [fileMetaQs]);

  const [uploadNote, setUploadNote] = React.useState("");
  const [file, setFile] = React.useState<File | null>(null);
  const inputRef = React.useRef<HTMLInputElement | null>(null);

  const uploadM = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error("Choose a file first.");
      const meta = await uploadFile(file);
      await addAttachment(requestId, {
        file_id: meta.id,
        note: uploadNote.trim() ? uploadNote.trim() : null,
      });
      return meta;
    },
    onSuccess: async () => {
      setUploadNote("");
      setFile(null);
      if (inputRef.current) inputRef.current.value = "";
      await qc.invalidateQueries({ queryKey: workflowKeys.request(requestId) });
    },
    onError: (err) => toastApiError(err),
  });

  const [downloadingId, setDownloadingId] = React.useState<string | null>(null);

  async function onDownload(fileId: UUID): Promise<void> {
    try {
      setDownloadingId(fileId);
      const meta = fileMetaById.get(fileId);
      const res = await downloadFile(fileId, {
        filename: meta?.original_filename,
      });
      saveBlobAsFile(res.blob, res.filename);
    } catch (err) {
      // apiDownload throws ApiError on failure; toast handles correlation ids.
      toastApiError(err);
    } finally {
      setDownloadingId(null);
    }
  }

  const uploadDisabledReason = !canReadFiles
    ? "Requires dms:file:read permission"
    : !canWriteFiles
      ? "Requires dms:file:write permission"
      : null;

  return (
    <RightPanelStack>
      <DSCard surface="panel" className="p-[var(--ds-space-16)]">
        <div className="text-sm font-medium text-text-1">Audit</div>
        <div className="mt-3">
          <AuditTimeline items={timelineItems(detail)} />
        </div>
      </DSCard>

      <DSCard surface="panel" className="p-[var(--ds-space-16)]">
        <div className="text-sm font-medium text-text-1">Attachments</div>
        <div className="mt-3 space-y-3 text-sm">
          {attachments.length === 0 ? (
            <div className="text-text-3">No attachments.</div>
          ) : (
            <div className="space-y-2">
              {attachments.map((a) => {
                const meta = fileMetaById.get(a.file_id);
                const label = meta?.original_filename ?? a.file_id;
                return (
                  <div
                    key={a.id}
                    className="flex items-center justify-between gap-2 rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 px-3 py-2"
                  >
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium text-text-1">
                        {label}
                      </div>
                      <div className="truncate text-xs text-text-3">
                        {a.note ? a.note : formatDateTime(a.created_at)}
                      </div>
                    </div>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      disabled={!canReadFiles || downloadingId === a.file_id}
                      onClick={() => void onDownload(a.file_id)}
                    >
                      {downloadingId === a.file_id
                        ? "Downloading..."
                        : "Download"}
                    </Button>
                  </div>
                );
              })}
            </div>
          )}

          <div className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-3">
            <div className="text-xs font-medium text-text-2">Upload</div>
            <div className="mt-2 space-y-2">
              <div className="space-y-1">
                <Label
                  htmlFor="wf-attachment-file"
                  className="text-xs text-text-2"
                >
                  File
                </Label>
                <input
                  id="wf-attachment-file"
                  ref={inputRef}
                  type="file"
                  disabled={Boolean(uploadDisabledReason) || uploadM.isPending}
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                />
              </div>
              <div className="space-y-1">
                <Label
                  htmlFor="wf-attachment-note"
                  className="text-xs text-text-2"
                >
                  Note (optional)
                </Label>
                <Input
                  id="wf-attachment-note"
                  value={uploadNote}
                  onChange={(e) => setUploadNote(e.target.value)}
                  disabled={Boolean(uploadDisabledReason) || uploadM.isPending}
                  placeholder={uploadDisabledReason ?? "Add a note..."}
                />
              </div>
              <Button
                type="button"
                variant="secondary"
                disabled={
                  Boolean(uploadDisabledReason) || !file || uploadM.isPending
                }
                onClick={() => uploadM.mutate()}
              >
                {uploadM.isPending ? "Uploading..." : "Upload & attach"}
              </Button>
              {uploadDisabledReason ? (
                <div className="text-xs text-text-3">
                  {uploadDisabledReason}
                </div>
              ) : null}
            </div>
          </div>
        </div>
      </DSCard>

      <DSCard surface="panel" className="p-[var(--ds-space-16)]">
        <div className="text-sm font-medium text-text-1">Comments</div>
        <div className="mt-3 space-y-3 text-sm">
          {detail.comments?.length ? (
            <div className="space-y-2">
              {detail.comments.map((c) => (
                <div
                  key={c.id}
                  className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 px-3 py-2"
                >
                  <div className="text-xs text-text-3">
                    {formatDateTime(c.created_at)}
                  </div>
                  <div className="mt-1 whitespace-pre-wrap text-sm text-text-1">
                    {c.body}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-text-3">No comments.</div>
          )}

          <div className="space-y-1">
            <Label htmlFor="wf-comment" className="text-xs text-text-2">
              Add comment
            </Label>
            <textarea
              id="wf-comment"
              className={[
                "min-h-20 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
              ].join(" ")}
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="Write a comment..."
              disabled={addCommentM.isPending}
            />
          </div>

          <Button
            type="button"
            variant="secondary"
            disabled={!comment.trim() || addCommentM.isPending}
            onClick={() => addCommentM.mutate()}
          >
            {addCommentM.isPending ? "Posting..." : "Post comment"}
          </Button>
        </div>
      </DSCard>
    </RightPanelStack>
  );
}
