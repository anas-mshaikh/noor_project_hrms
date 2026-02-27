"use client";

import * as React from "react";
import { Inbox } from "lucide-react";

import { DSCard } from "@/components/ds/DSCard";
import { AuditTimeline } from "@/components/ds/AuditTimeline";
import { PageHeader } from "@/components/ds/PageHeader";
import { WorkbenchTemplate } from "@/components/ds/templates/WorkbenchTemplate";
import { EmptyState } from "@/components/ds/EmptyState";
import { Skeleton } from "@/components/ui/skeleton";

export default function InboxPage() {
  return (
    <WorkbenchTemplate
      header={
        <PageHeader
          title="Inbox"
          subtitle="Team and system threads. (UI scaffold)"
        />
      }
      list={
        <DSCard surface="panel" className="p-[var(--ds-space-16)]">
          <div className="text-sm font-medium text-text-1">Threads</div>
          <div className="mt-3 space-y-2">
            {Array.from({ length: 7 }).map((_, i) => (
              <div
                key={i}
                className="flex items-center gap-3 rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 px-[var(--ds-space-16)]"
                style={{ height: "var(--ds-row-h)" }}
              >
                <Skeleton className="h-8 w-8 rounded-full" />
                <div className="min-w-0 flex-1 space-y-2">
                  <Skeleton className="h-3 w-40" />
                  <Skeleton className="h-3 w-24" />
                </div>
              </div>
            ))}
          </div>
        </DSCard>
      }
      detail={
        <DSCard surface="card" className="p-[var(--ds-space-20)]">
          <EmptyState
            icon={Inbox}
            title="No thread selected"
            description="This is a workbench scaffold. Threads, search, and attachments will be wired in a later milestone."
            align="center"
          />
        </DSCard>
      }
      context={
        <DSCard surface="panel" className="p-[var(--ds-space-16)]">
          <div className="text-sm font-medium text-text-1">Trust cues</div>
          <div className="mt-3 text-sm text-text-2">
            When wired, this panel will show audit + workflow context for the
            selected thread.
          </div>
          <div className="mt-4">
            <AuditTimeline
              items={[
                {
                  title: "Request created",
                  time: "09:14",
                  description: "A workflow request was submitted.",
                  tone: "info",
                },
                {
                  title: "Assigned to you",
                  time: "09:15",
                  description: "You are a participant in this request.",
                  tone: "warning",
                },
                {
                  title: "Decision recorded",
                  time: "09:47",
                  description: "Approved by manager.",
                  tone: "success",
                },
              ]}
            />
          </div>
        </DSCard>
      }
    />
  );
}

