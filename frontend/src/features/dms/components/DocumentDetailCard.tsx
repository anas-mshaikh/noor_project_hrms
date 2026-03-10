"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";

import { saveBlobAsFile } from "@/lib/api";
import { toastApiError } from "@/lib/toastApiError";
import type { DmsDocumentOut } from "@/lib/types";
import { downloadFile, getFileMeta } from "@/features/dms/api/files";
import { expiryLabel } from "@/features/dms/expiry";
import { dmsKeys } from "@/features/dms/queryKeys";

import { DSCard } from "@/components/ds/DSCard";
import { StatusChip } from "@/components/ds/StatusChip";
import { Button } from "@/components/ui/button";

function formatDate(value: string | null | undefined): string {
  if (!value) return "-";
  try {
    return new Date(value).toLocaleDateString();
  } catch {
    return value;
  }
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) return "-";
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

export function DocumentDetailCard({
  document,
  canReadFiles,
  footer,
  notFoundCopy,
}: {
  document: DmsDocumentOut;
  canReadFiles: boolean;
  footer?: React.ReactNode;
  notFoundCopy?: React.ReactNode;
}) {
  const currentFileId = document.current_version?.file_id ?? null;
  const fileMetaQ = useQuery({
    queryKey: dmsKeys.fileMeta(currentFileId),
    enabled: Boolean(canReadFiles && currentFileId),
    queryFn: () => getFileMeta(currentFileId as string),
  });

  const [downloading, setDownloading] = React.useState(false);

  async function onDownload() {
    if (!currentFileId) return;
    try {
      setDownloading(true);
      const res = await downloadFile(currentFileId, {
        filename: fileMetaQ.data?.original_filename,
      });
      saveBlobAsFile(res.blob, res.filename);
    } catch (err) {
      toastApiError(err);
    } finally {
      setDownloading(false);
    }
  }

  return (
    <div className="space-y-4">
      <DSCard surface="panel" className="p-[var(--ds-space-16)]">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="text-base font-semibold tracking-tight text-text-1">
              {document.document_type_name}
            </div>
            <div className="mt-1 text-sm text-text-2">{document.document_type_code}</div>
          </div>
          <StatusChip status={document.status} />
        </div>

        <div className="mt-4 grid gap-3 text-sm md:grid-cols-2">
          <div className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-3">
            <div className="text-xs text-text-2">Created</div>
            <div className="mt-1 text-text-1">{formatDateTime(document.created_at)}</div>
          </div>
          <div className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-3">
            <div className="text-xs text-text-2">Expiry</div>
            <div className="mt-1 text-text-1">{document.expires_at ? formatDate(document.expires_at) : "No expiry"}</div>
            {document.expires_at ? <div className="mt-1 text-xs text-text-3">{expiryLabel(Math.ceil((new Date(document.expires_at).getTime() - Date.now()) / 86400000))}</div> : null}
          </div>
          <div className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-3">
            <div className="text-xs text-text-2">Current version</div>
            <div className="mt-1 text-text-1">v{document.current_version?.version ?? 0}</div>
            <div className="mt-1 text-xs text-text-3">Current version only in V0</div>
          </div>
          <div className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-3">
            <div className="text-xs text-text-2">Workflow</div>
            {document.verification_workflow_request_id ? (
              <Link
                href={`/workflow/requests/${document.verification_workflow_request_id}`}
                className="mt-1 inline-flex text-text-1 hover:underline"
              >
                Open verification request
              </Link>
            ) : (
              <div className="mt-1 text-text-2">No verification request yet</div>
            )}
          </div>
        </div>
      </DSCard>

      <DSCard surface="panel" className="p-[var(--ds-space-16)]">
        <div className="text-sm font-medium text-text-1">Current document</div>
        {document.current_version ? (
          <div className="mt-3 space-y-3 text-sm">
            <div className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-3">
              <div className="text-xs text-text-2">File name</div>
              <div className="mt-1 text-text-1">{fileMetaQ.data?.original_filename ?? (canReadFiles ? "Loading..." : "Available in document view")}</div>
            </div>
            <div className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-3">
              <div className="text-xs text-text-2">Uploaded</div>
              <div className="mt-1 text-text-1">{formatDateTime(document.current_version.created_at)}</div>
            </div>
            {document.current_version.notes ? (
              <div className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-3">
                <div className="text-xs text-text-2">Notes</div>
                <div className="mt-1 whitespace-pre-wrap text-text-1">{document.current_version.notes}</div>
              </div>
            ) : null}
            <div className="flex flex-wrap items-center gap-2">
              <Button type="button" variant="secondary" disabled={!currentFileId || !canReadFiles || downloading} onClick={() => void onDownload()}>
                {downloading ? "Downloading..." : "Download current document"}
              </Button>
            </div>
          </div>
        ) : (
          notFoundCopy ?? <div className="mt-3 text-sm text-text-3">No current version.</div>
        )}
      </DSCard>

      {footer ? <div>{footer}</div> : null}
    </div>
  );
}
