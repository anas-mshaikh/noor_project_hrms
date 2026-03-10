"use client";

import * as React from "react";

import { DSCard } from "@/components/ds/DSCard";

export function PayrollSummaryCard({
  label,
  value,
  hint,
}: {
  label: string;
  value: React.ReactNode;
  hint?: React.ReactNode;
}) {
  return (
    <DSCard surface="panel" className="p-[var(--ds-space-16)]">
      <div className="text-xs text-text-2">{label}</div>
      <div className="mt-2 text-lg font-semibold tracking-tight text-text-1">{value}</div>
      {hint ? <div className="mt-2 text-xs text-text-3">{hint}</div> : null}
    </DSCard>
  );
}
