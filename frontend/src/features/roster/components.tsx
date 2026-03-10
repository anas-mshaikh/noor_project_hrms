"use client";

import * as React from "react";
import Link from "next/link";

import type { EmployeeDirectoryRowOut, UUID } from "@/lib/types";

import { DataTable } from "@/components/ds/DataTable";
import { DSCard } from "@/components/ds/DSCard";
import { EmptyState } from "@/components/ds/EmptyState";
import { FilterBar } from "@/components/ds/FilterBar";
import { StatusChip } from "@/components/ds/StatusChip";
import { StorePicker } from "@/components/StorePicker";
import { Button } from "@/components/ui/button";

export function BranchScopeState({
  title = "Select a branch",
  description = "Roster data is branch-scoped. Select a company and branch to continue.",
}: {
  title?: string;
  description?: string;
}) {
  return (
    <DSCard surface="card" className="space-y-4 p-[var(--ds-space-20)]">
      <EmptyState
        title={title}
        description={description}
        primaryAction={
          <Button asChild variant="secondary">
            <Link href="/scope">Go to scope</Link>
          </Button>
        }
      />
      <StorePicker />
    </DSCard>
  );
}

export function EmployeePickerCard({
  employees,
  isLoading,
  error,
  onRetry,
  search,
  onSearch,
  onSelect,
}: {
  employees: EmployeeDirectoryRowOut[];
  isLoading: boolean;
  error: unknown;
  onRetry: () => void;
  search: string;
  onSearch: (value: string) => void;
  onSelect: (employeeId: UUID) => void;
}) {
  return (
    <DataTable
      toolbar={
        <FilterBar
          search={{
            value: search,
            onChange: onSearch,
            placeholder: "Search employees by code or name...",
            disabled: isLoading,
          }}
          onClearAll={search ? () => onSearch("") : undefined}
          clearDisabled={isLoading}
        />
      }
      isLoading={isLoading}
      error={error}
      onRetry={onRetry}
      isEmpty={!isLoading && !error && employees.length === 0}
      emptyState={
        <EmptyState
          title="Select an employee"
          description="Choose an employee to continue."
          align="center"
        />
      }
      skeleton={{ rows: 6, cols: 3 }}
    >
      <div className="space-y-2">
        {employees.map((employee) => (
          <button
            key={employee.employee_id}
            type="button"
            className="flex w-full items-center justify-between rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 px-4 py-3 text-left hover:bg-surface-2"
            onClick={() => onSelect(employee.employee_id)}
          >
            <div className="min-w-0">
              <div className="truncate text-sm font-medium text-text-1">{employee.full_name}</div>
              <div className="mt-1 text-xs text-text-2">{employee.employee_code}</div>
            </div>
            <StatusChip status={employee.status} />
          </button>
        ))}
      </div>
    </DataTable>
  );
}
