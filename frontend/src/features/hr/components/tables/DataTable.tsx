"use client";

import * as React from "react";

import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";
import { GlassCard } from "@/features/hr/components/cards/GlassCard";

export type DataColumn<T> = {
  key: string;
  header: string;
  className?: string;
  cell: (row: T) => React.ReactNode;
};

type DataTableProps<T> = {
  columns: Array<DataColumn<T>>;
  rows: T[];
  rowKey: (row: T) => string;
  loading?: boolean;
  skeletonRows?: number;
  emptyTitle?: string;
  emptyDescription?: string;
  className?: string;
};

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  loading,
  skeletonRows = 6,
  emptyTitle = "No rows",
  emptyDescription = "Nothing to show yet.",
  className,
}: DataTableProps<T>) {
  return (
    <GlassCard className={cn("p-0", className)}>
      <div className="grid grid-cols-12 gap-3 border-b border-white/10 px-5 py-3 text-xs font-medium text-muted-foreground">
        {columns.map((c) => (
          <div key={c.key} className={cn("col-span-3", c.className)}>
            {c.header}
          </div>
        ))}
      </div>

      <div className="p-2">
        {loading ? (
          <div className="space-y-2 p-3">
            {Array.from({ length: skeletonRows }).map((_, i) => (
              <div
                key={i}
                className="grid grid-cols-12 gap-3 rounded-2xl bg-white/[0.02] p-3 ring-1 ring-white/5"
              >
                {columns.map((c) => (
                  <div key={c.key} className={cn("col-span-3", c.className)}>
                    <Skeleton className="h-4 w-24 bg-white/10" />
                  </div>
                ))}
              </div>
            ))}
          </div>
        ) : rows.length === 0 ? (
          <div className="p-5">
            <div className="text-sm font-semibold tracking-tight">{emptyTitle}</div>
            <div className="mt-1 text-sm text-muted-foreground">{emptyDescription}</div>
          </div>
        ) : (
          <div className="space-y-2 p-3">
            {rows.map((row) => (
              <div
                key={rowKey(row)}
                className="grid grid-cols-12 gap-3 rounded-2xl bg-white/[0.02] p-3 ring-1 ring-white/5"
              >
                {columns.map((c) => (
                  <div key={c.key} className={cn("col-span-3", c.className)}>
                    {c.cell(row)}
                  </div>
                ))}
              </div>
            ))}
          </div>
        )}
      </div>
    </GlassCard>
  );
}

