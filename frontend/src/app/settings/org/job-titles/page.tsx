"use client";

import * as React from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/lib/auth";
import { useSelection } from "@/lib/selection";
import { toastApiError } from "@/lib/toastApiError";
import type { JobTitleCreate, JobTitleOut, UUID } from "@/lib/types";
import { createJobTitle, listJobTitles } from "@/features/tenancy/api/tenancy";
import { tenancyKeys } from "@/features/tenancy/queryKeys";

import { DataTable } from "@/components/ds/DataTable";
import { DSCard } from "@/components/ds/DSCard";
import { EmptyState } from "@/components/ds/EmptyState";
import { PageHeader } from "@/components/ds/PageHeader";
import { RightPanelStack } from "@/components/ds/RightPanelStack";
import { ListRightPanelTemplate } from "@/components/ds/templates/ListRightPanelTemplate";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export default function JobTitlesPage() {
  const companyId = useSelection((s) => s.companyId);

  const permissions = useAuth((s) => s.permissions);
  const canWrite = React.useMemo(
    () => new Set(permissions ?? []).has("tenancy:write"),
    [permissions]
  );

  const qc = useQueryClient();

  const titlesQ = useQuery({
    queryKey: companyId ? tenancyKeys.jobTitles(companyId) : ["tenancy", "job-titles", "missing-company"],
    enabled: Boolean(companyId),
    queryFn: () => listJobTitles({ companyId: companyId as UUID }),
  });

  const titles = (titlesQ.data ?? []) as JobTitleOut[];

  const [open, setOpen] = React.useState(false);
  const [name, setName] = React.useState("");

  const createM = useMutation({
    mutationFn: async () => {
      if (!companyId) throw new Error("Company selection is required.");
      const payload: JobTitleCreate = { company_id: companyId, name: name.trim() };
      if (!payload.name) throw new Error("Job title name is required.");
      return createJobTitle(payload);
    },
    onSuccess: async () => {
      setOpen(false);
      setName("");
      if (companyId) {
        await qc.invalidateQueries({ queryKey: tenancyKeys.jobTitles(companyId) });
      }
    },
    onError: (err) => toastApiError(err),
  });

  if (!companyId) {
    return (
      <EmptyState
        title="Select a company"
        description="Job titles are company-scoped. Select a company from the scope picker to continue."
        primaryAction={
          <Button asChild variant="secondary">
            <Link href="/scope">Go to scope</Link>
          </Button>
        }
      />
    );
  }

  return (
    <ListRightPanelTemplate
      header={
        <PageHeader
          title="Job Titles"
          subtitle="Catalog used for HR profiles and future policy rules."
          actions={
            <Sheet open={open} onOpenChange={setOpen}>
              <SheetTrigger asChild>
                <Button type="button" disabled={!canWrite}>
                  Create title
                </Button>
              </SheetTrigger>
              <SheetContent className="border-border-subtle bg-surface-2 backdrop-blur-xl">
                <SheetHeader>
                  <SheetTitle>Create job title</SheetTitle>
                  <SheetDescription>Add a title under the selected company.</SheetDescription>
                </SheetHeader>

                <div className="space-y-4 px-4">
                  <div className="space-y-1">
                    <Label htmlFor="job-title-name" className="text-xs text-text-2">
                      Name
                    </Label>
                    <Input
                      id="job-title-name"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                    />
                  </div>
                </div>

                <SheetFooter>
                  <Button
                    type="button"
                    disabled={!canWrite || createM.isPending}
                    onClick={() => createM.mutate()}
                  >
                    {createM.isPending ? "Creating..." : "Create"}
                  </Button>
                </SheetFooter>
              </SheetContent>
            </Sheet>
          }
        />
      }
      main={
        <DataTable
          isLoading={titlesQ.isLoading}
          error={titlesQ.error}
          onRetry={titlesQ.refetch}
          isEmpty={!titlesQ.isLoading && !titlesQ.error && titles.length === 0}
          emptyState={
            <EmptyState
              title="No job titles yet"
              description="Create your first job title to start standardizing roles."
              primaryAction={
                canWrite ? (
                  <Button type="button" onClick={() => setOpen(true)}>
                    Create title
                  </Button>
                ) : null
              }
            />
          }
          skeleton={{ rows: 6, cols: 2 }}
        >
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>ID</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {titles.map((t) => (
                <TableRow key={t.id}>
                  <TableCell className="font-medium">{t.name}</TableCell>
                  <TableCell className="font-mono text-xs text-text-3">{t.id}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </DataTable>
      }
      right={
        <RightPanelStack>
          <DSCard surface="panel" className="p-[var(--ds-space-20)]">
            <div className="text-sm font-semibold tracking-tight text-text-1">
              Notes
            </div>
            <div className="mt-2 text-sm text-text-2">
              Job titles are intentionally simple in v1. In future milestones, we can link them to compensation, roster rules, and org policies.
            </div>
          </DSCard>

          <DSCard surface="panel" className="p-[var(--ds-space-20)]">
            <div className="text-sm font-semibold tracking-tight text-text-1">
              Summary
            </div>
            <div className="mt-2 grid grid-cols-2 gap-3 text-sm">
              <div className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-3">
                <div className="text-xs text-text-2">titles</div>
                <div className="mt-1 text-lg font-semibold text-text-1">{titles.length}</div>
              </div>
              <div className="rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 p-3">
                <div className="text-xs text-text-2">company</div>
                <div className="mt-1 text-sm font-medium text-text-1">Selected</div>
              </div>
            </div>
          </DSCard>
        </RightPanelStack>
      }
    />
  );
}

