"use client";

/**
 * components/ds/FilterBar.tsx
 *
 * Standard list toolbar:
 * - search input (optional)
 * - chips row (optional)
 * - date range slot (optional)
 * - right actions (optional)
 * - clear all (optional)
 */

import * as React from "react";

import { cn } from "@/lib/utils";
import { DSCard } from "@/components/ds/DSCard";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export type FilterBarProps = {
  search?: {
    value: string;
    onChange: (v: string) => void;
    placeholder?: string;
    disabled?: boolean;
  };
  chips?: React.ReactNode;
  dateRangeSlot?: React.ReactNode;
  rightActions?: React.ReactNode;
  onClearAll?: () => void;
  clearDisabled?: boolean;
  className?: string;
};

export function FilterBar({
  search,
  chips,
  dateRangeSlot,
  rightActions,
  onClearAll,
  clearDisabled,
  className,
}: FilterBarProps) {
  return (
    <DSCard
      surface="panel"
      className={cn("p-[var(--ds-space-16)]", className)}
    >
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="flex min-w-0 flex-1 flex-col gap-3 md:flex-row md:items-center">
          {search ? (
            <div className="min-w-0 md:w-80">
              <Input
                value={search.value}
                onChange={(e) => search.onChange(e.target.value)}
                placeholder={search.placeholder ?? "Search..."}
                disabled={search.disabled}
              />
            </div>
          ) : null}

          {dateRangeSlot ? <div className="shrink-0">{dateRangeSlot}</div> : null}

          {chips ? (
            <div className="flex flex-wrap items-center gap-2">{chips}</div>
          ) : null}
        </div>

        <div className="flex shrink-0 flex-wrap items-center gap-2">
          {rightActions}
          {onClearAll ? (
            <Button
              type="button"
              variant="ghost"
              onClick={onClearAll}
              disabled={Boolean(clearDisabled)}
            >
              Clear all
            </Button>
          ) : null}
        </div>
      </div>
    </DSCard>
  );
}

