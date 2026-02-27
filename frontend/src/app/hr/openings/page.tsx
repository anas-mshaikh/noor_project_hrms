"use client";

import * as React from "react";
import Link from "next/link";
import { Filter, FolderOpen, Plus } from "lucide-react";
import { useTranslation } from "@/lib/i18n";

import { useSelection } from "@/lib/selection";
import { useOpenings } from "@/features/hr/hooks/useOpenings";
import type { OpeningOut } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { StorePicker } from "@/components/StorePicker";

import { DataView } from "@/components/ds/DataView";
import { DataTable } from "@/components/ds/DataTable";
import { EmptyState } from "@/components/ds/EmptyState";
import { FilterBar } from "@/components/ds/FilterBar";
import { PageHeader } from "@/components/ds/PageHeader";
import { StatusChip } from "@/components/ds/StatusChip";

type FilterKey = "ACTIVE" | "ARCHIVED" | "ALL";

function yyyyMmDd(ts: string): string {
  return ts.includes("T") ? ts.split("T")[0] : ts;
}

function statusPill(
  filter: FilterKey,
  active: FilterKey,
  onClick: (k: FilterKey) => void
): React.ReactNode {
  const isActive = filter === active;
  return (
    <button
      key={filter}
      type="button"
      onClick={() => onClick(filter)}
      className={
        isActive
          ? "rounded-full border border-border-strong bg-surface-2 px-3 py-1 text-xs text-text-1 shadow-[var(--ds-elevation-panel)]"
          : "rounded-full border border-border-subtle bg-surface-1 px-3 py-1 text-xs text-text-2 hover:bg-surface-2"
      }
      aria-label={`Filter ${filter.toLowerCase()}`}
    >
      {filter}
    </button>
  );
}

export default function HROpeningsPage() {
  const { t } = useTranslation();
  const branchId = useSelection((s) => s.branchId);
  const { list } = useOpenings(branchId ?? null);

  const [filter, setFilter] = React.useState<FilterKey>("ACTIVE");
  const [q, setQ] = React.useState("");

  const openingsRaw = (list.data ?? []) as OpeningOut[];

  const openings = openingsRaw
    .filter((o) => (filter === "ALL" ? true : o.status === filter))
    .filter((o) => {
      if (!q.trim()) return true;
      return o.title.toLowerCase().includes(q.trim().toLowerCase());
    });

  const isEmpty = Boolean(branchId) && !list.isPending && openings.length === 0;

  const header = (
    <PageHeader
      title={t("hr.openings_page.title", { defaultValue: "Openings" })}
      subtitle={t("hr.openings_page.subtitle", {
        defaultValue: "Create openings, upload resumes, and run AI screening.",
      })}
      actions={
        branchId ? (
          <Button asChild>
            <Link href="/hr/openings/new">
              <Plus className="h-4 w-4" />
              {t("hr.openings_page.create_opening", { defaultValue: "Create Opening" })}
            </Link>
          </Button>
        ) : (
          <Button disabled>
            <Plus className="h-4 w-4" />
            {t("hr.openings_page.create_opening", { defaultValue: "Create Opening" })}
          </Button>
        )
      }
      meta={
        branchId ? (
          <span className="rounded-full border border-border-subtle bg-surface-1 px-3 py-1 text-xs text-text-2">
            branch_id: {branchId}
          </span>
        ) : (
          <span className="rounded-full border border-border-subtle bg-surface-1 px-3 py-1 text-xs text-text-2">
            {t("hr.common.select_branch", { defaultValue: "Select a branch" })}
          </span>
        )
      }
    />
  );

  if (!branchId) {
    return (
      <DataView
        header={header}
      >
        <div className="max-w-2xl">
          <EmptyState
            icon={FolderOpen}
            title={t("hr.openings_page.empty_title", {
              defaultValue: "Select a branch to manage openings",
            })}
            description={t("hr.openings_page.empty_description", {
              defaultValue:
                "HR Openings are branch-scoped. Pick a branch to view and create openings.",
            })}
            primaryAction={<div className="w-full"><StorePicker /></div>}
          />
        </div>
      </DataView>
    );
  }

  return (
    <DataView header={header}>
      <DataTable
        toolbar={
          <FilterBar
            search={{
              value: q,
              onChange: setQ,
              placeholder: t("common.search", { defaultValue: "Search..." }),
            }}
            chips={
              <div className="flex flex-wrap items-center gap-2">
                {statusPill("ACTIVE", filter, setFilter)}
                {statusPill("ARCHIVED", filter, setFilter)}
                {statusPill("ALL", filter, setFilter)}
              </div>
            }
            rightActions={
              <Tooltip>
                <TooltipTrigger asChild>
                  <span className="inline-flex">
                    <Button type="button" variant="outline" disabled>
                      <Filter className="h-4 w-4" />
                      {t("hr.common.filters", { defaultValue: "Filters" })}
                    </Button>
                  </span>
                </TooltipTrigger>
                <TooltipContent side="bottom" sideOffset={10}>
                  {t("common.not_available_v0", { defaultValue: "Not available in Client V0" })}
                </TooltipContent>
              </Tooltip>
            }
            onClearAll={() => {
              setQ("");
              setFilter("ACTIVE");
            }}
            clearDisabled={!q.trim() && filter === "ACTIVE"}
          />
        }
        isLoading={list.isPending}
        error={list.isError ? list.error : undefined}
        isEmpty={isEmpty}
        onRetry={() => list.refetch()}
        emptyState={
          <EmptyState
            icon={FolderOpen}
            title={t("hr.openings_page.no_openings_title", {
              defaultValue: "No openings found",
            })}
            description={t("hr.openings_page.no_openings_description", {
              defaultValue:
                "Create an opening to start collecting resumes and screening candidates.",
            })}
            primaryAction={
              <Button asChild>
                <Link href="/hr/openings/new">
                  {t("hr.openings_page.create_opening", { defaultValue: "Create Opening" })}
                </Link>
              </Button>
            }
          />
        }
      >
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Title</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Created</TableHead>
              <TableHead className="text-end">Open</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {openings.map((o) => (
              <TableRow key={o.id}>
                <TableCell className="font-medium">
                  <Link
                    href={`/hr/openings/${o.id}`}
                    className="hover:underline"
                  >
                    {o.title}
                  </Link>
                </TableCell>
                <TableCell>
                  <StatusChip status={String(o.status ?? "-")} />
                </TableCell>
                <TableCell className="whitespace-nowrap text-text-2">
                  {yyyyMmDd(o.created_at)}
                </TableCell>
                <TableCell className="text-end">
                  <Button asChild size="sm" variant="secondary">
                    <Link href={`/hr/openings/${o.id}`}>View</Link>
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </DataTable>
    </DataView>
  );
}
