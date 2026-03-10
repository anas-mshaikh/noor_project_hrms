"use client";

import * as React from "react";
import Link from "next/link";

import { payloadToRows } from "@/features/workflow/payload";
import { workflowRequestTypeLabel } from "@/features/workflow/requestTypes";
import { workflowStatusLabel } from "@/features/workflow/status";
import type { WorkflowRequestDetailOut } from "@/lib/types";
import { compatibilityDocHref } from "@/features/dms/routes";

import { StatusChip } from "@/components/ds/StatusChip";
import { Button } from "@/components/ui/button";

function formatDateTime(value: string): string {
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

export function WorkflowRequestDetailCard({
  detail,
  actions,
}: {
  detail: WorkflowRequestDetailOut;
  actions?: React.ReactNode;
}) {
  const req = detail.request;
  const rows = payloadToRows(req.payload ?? {}, req.request_type_code);
  const openDocHref =
    req.entity_type === "dms.document" && req.entity_id
      ? compatibilityDocHref({
          docId: req.entity_id,
          employeeId: req.subject_employee_id ?? null,
        })
      : null;

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="text-base font-semibold tracking-tight text-text-1">
            {workflowRequestTypeLabel(req.request_type_code)}
          </div>
          <StatusChip status={req.status} />
        </div>
        <div className="text-sm text-text-2">
          {workflowStatusLabel(req.status)} • {formatDateTime(req.created_at)}
        </div>
      </div>

      {req.subject ? (
        <div className="space-y-1">
          <div className="text-xs font-medium text-text-2">Subject</div>
          <div className="text-sm text-text-1">{req.subject}</div>
        </div>
      ) : null}

      <div className="space-y-2">
        <div className="text-xs font-medium text-text-2">Payload</div>
        {rows.length === 0 ? (
          <div className="text-sm text-text-3">No payload fields.</div>
        ) : (
          <div className="space-y-2">
            {rows.map((r) => (
              <div
                key={r.key}
                className="flex items-start justify-between gap-3"
              >
                <div className="text-xs font-medium text-text-2">{r.key}</div>
                <div className="max-w-[70%] break-words text-right text-sm text-text-1">
                  {r.value}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {openDocHref ? (
        <div>
          <Button asChild type="button" variant="secondary">
            <Link href={openDocHref}>Open document</Link>
          </Button>
        </div>
      ) : null}

      {actions ? <div>{actions}</div> : null}
    </div>
  );
}
