"use client";

import * as React from "react";
import { CheckCircle2, Loader2, OctagonAlert, UploadCloud } from "lucide-react";

import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";

export type BatchItemStatus = "UPLOADED" | "PARSING" | "PARSED" | "FAILED";

export type BatchProgressItem = {
  id: string;
  filename: string;
  status: BatchItemStatus;
  error?: string | null;
};

type BatchProgressProps = {
  items: BatchProgressItem[];
  loading?: boolean;
  className?: string;
};

function iconFor(status: BatchItemStatus) {
  if (status === "PARSED") return <CheckCircle2 className="h-4 w-4 text-emerald-300" />;
  if (status === "FAILED") return <OctagonAlert className="h-4 w-4 text-rose-300" />;
  if (status === "PARSING") return <Loader2 className="h-4 w-4 animate-spin text-violet-200" />;
  return <UploadCloud className="h-4 w-4 text-muted-foreground" />;
}

export function BatchProgress({ items, loading, className }: BatchProgressProps) {
  return (
    <div className={cn("space-y-2", className)}>
      {loading ? (
        <>
          {Array.from({ length: 4 }).map((_, i) => (
            <div
              key={i}
              className="flex items-center justify-between gap-3 rounded-2xl bg-white/[0.02] p-3 ring-1 ring-white/5"
            >
              <div className="flex items-center gap-3">
                <Skeleton className="h-9 w-9 rounded-xl bg-white/10" />
                <div className="space-y-2">
                  <Skeleton className="h-3 w-48 bg-white/10" />
                  <Skeleton className="h-3 w-28 bg-white/10" />
                </div>
              </div>
              <Skeleton className="h-3 w-16 bg-white/10" />
            </div>
          ))}
        </>
      ) : items.length === 0 ? (
        <div className="rounded-2xl bg-white/[0.02] p-4 text-sm text-muted-foreground ring-1 ring-white/5">
          No uploads yet.
        </div>
      ) : (
        items.map((it) => (
          <div
            key={it.id}
            className="flex items-center justify-between gap-3 rounded-2xl bg-white/[0.02] p-3 ring-1 ring-white/5"
          >
            <div className="flex min-w-0 items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-white/5 ring-1 ring-white/10">
                {iconFor(it.status)}
              </div>
              <div className="min-w-0">
                <div className="truncate text-sm font-medium">{it.filename}</div>
                <div className="truncate text-xs text-muted-foreground">
                  {it.status === "FAILED" && it.error ? it.error : it.status}
                </div>
              </div>
            </div>

            <div className="shrink-0 text-xs text-muted-foreground">
              {it.status === "PARSED" ? "Ready" : it.status}
            </div>
          </div>
        ))
      )}
    </div>
  );
}

