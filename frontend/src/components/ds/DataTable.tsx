"use client";

/**
 * components/ds/DataTable.tsx
 *
 * Wrapper around the existing Table primitive providing:
 * - toolbar slot
 * - loading skeleton
 * - empty state
 * - error state
 *
 * This keeps page code consistent without re-inventing table rendering.
 */

import * as React from "react";

import type { DensityMode } from "@/design-system/density";
import { densityClassName } from "@/design-system/density";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";
import { DSCard } from "@/components/ds/DSCard";
import { EmptyState } from "@/components/ds/EmptyState";
import { ErrorState } from "@/components/ds/ErrorState";

function TableSkeleton({
  rows,
  cols,
}: {
  rows: number;
  cols: number;
}) {
  return (
    <div className="space-y-2">
      {Array.from({ length: rows }).map((_, r) => (
        <div
          key={r}
          className="flex items-center gap-3 rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 px-[var(--ds-row-px)]"
          style={{ height: "var(--ds-row-h)" }}
        >
          {Array.from({ length: cols }).map((__, c) => (
            <Skeleton
              key={c}
              className={cn(
                "h-3",
                c === 0 ? "w-48" : c === cols - 1 ? "w-16" : "w-24"
              )}
            />
          ))}
        </div>
      ))}
    </div>
  );
}

export function DataTable({
  toolbar,
  isLoading,
  error,
  isEmpty,
  emptyState,
  onRetry,
  density = "comfortable",
  skeleton = { rows: 6, cols: 4 },
  children,
  className,
}: {
  toolbar?: React.ReactNode;
  isLoading: boolean;
  error?: unknown;
  isEmpty: boolean;
  emptyState?: React.ReactNode;
  onRetry?: () => void;
  density?: DensityMode;
  skeleton?: { rows?: number; cols?: number };
  children: React.ReactNode;
  className?: string;
}) {
  const rows = skeleton.rows ?? 6;
  const cols = skeleton.cols ?? 4;

  return (
    <div className={cn("space-y-4", densityClassName(density), className)}>
      {toolbar ? <div>{toolbar}</div> : null}

      <DSCard surface="card" className="p-[var(--ds-space-20)]">
        {isLoading ? (
          <TableSkeleton rows={rows} cols={cols} />
        ) : error ? (
          <ErrorState
            title="Could not load data"
            error={error}
            onRetry={onRetry}
            variant="inline"
            className="max-w-none"
          />
        ) : isEmpty ? (
          emptyState ?? (
            <EmptyState
              title="No results"
              description="Try adjusting filters or create your first record."
            />
          )
        ) : (
          children
        )}
      </DSCard>
    </div>
  );
}
