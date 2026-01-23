"use client";

import * as React from "react";

import type { HrOnboardingDoc } from "@/features/hr/mock/types";
import { cn } from "@/lib/utils";

type DocumentTileProps = {
  doc: HrOnboardingDoc;
  className?: string;
};

function dotClass(status: HrOnboardingDoc["status"]): string {
  if (status === "VERIFIED") return "bg-emerald-300";
  if (status === "REJECTED") return "bg-rose-300";
  if (status === "UPLOADED") return "bg-violet-300";
  return "bg-white/30";
}

export function DocumentTile({ doc, className }: DocumentTileProps) {
  return (
    <div
      className={cn(
        "flex items-center justify-between gap-3 rounded-2xl bg-white/[0.02] p-4 ring-1 ring-white/5",
        className
      )}
    >
      <div className="min-w-0">
        <div className="text-sm font-medium">{doc.doc_type}</div>
        <div className="mt-1 text-xs text-muted-foreground">{doc.status}</div>
      </div>
      <div className={cn("h-2.5 w-2.5 rounded-full", dotClass(doc.status))} />
    </div>
  );
}

