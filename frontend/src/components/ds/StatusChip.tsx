"use client";

/**
 * components/ds/StatusChip.tsx
 *
 * Small status pill with semantic coloring.
 */

import * as React from "react";

import { cn } from "@/lib/utils";

type Tone = "neutral" | "success" | "warning" | "danger" | "info";

function toneForStatus(status: string): Tone {
  switch (status.toUpperCase()) {
    case "APPROVED":
    case "ACTIVE":
    case "VERIFIED":
    case "PUBLISHED":
      return "success";
    case "PENDING":
    case "IN_REVIEW":
    case "DRAFT":
      return "warning";
    case "REJECTED":
    case "FAILED":
      return "danger";
    case "CANCELED":
    case "CANCELLED":
    case "INACTIVE":
      return "neutral";
    default:
      return "info";
  }
}

function toneClassName(tone: Tone): string {
  switch (tone) {
    case "success":
      return "border-success/30 bg-success/10 text-success";
    case "warning":
      return "border-warning/30 bg-warning/10 text-warning";
    case "danger":
      return "border-danger/30 bg-danger/10 text-danger";
    case "info":
      return "border-info/30 bg-info/10 text-info";
    case "neutral":
    default:
      return "border-border-subtle bg-surface-1 text-text-2";
  }
}

export function StatusChip({
  status,
  className,
}: {
  status: string;
  className?: string;
}) {
  const tone = toneForStatus(status);
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium",
        toneClassName(tone),
        className
      )}
    >
      {status}
    </span>
  );
}

