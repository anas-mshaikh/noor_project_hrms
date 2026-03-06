"use client";

import * as React from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useSelection } from "@/lib/selection";
import { toastApiError } from "@/lib/toastApiError";
import type { UUID, WorkflowDefinitionCreateIn, WorkflowDefinitionOut } from "@/lib/types";
import { createDefinition, listDefinitions } from "@/features/workflow/api/workflow";
import { workflowKeys } from "@/features/workflow/queryKeys";

import { DataTable } from "@/components/ds/DataTable";
import { EmptyState } from "@/components/ds/EmptyState";
import { ErrorState } from "@/components/ds/ErrorState";
import { FilterBar } from "@/components/ds/FilterBar";
import { StatusChip } from "@/components/ds/StatusChip";
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

export default function WorkflowDefinitionsPage() {
  const qc = useQueryClient();
  const companyId = useSelection((s) => s.companyId) as UUID | undefined;

  const defsQ = useQuery({
    queryKey: workflowKeys.definitions(companyId ?? null),
    queryFn: () => listDefinitions({ companyId: companyId ?? null }),
  });

  const items = (defsQ.data ?? []) as WorkflowDefinitionOut[];

  const [q, setQ] = React.useState("");
  const filtered = React.useMemo(() => {
    const term = q.trim().toLowerCase();
    if (!term) return items;
    return items.filter((d) => {
      const hay = `${d.request_type_code} ${d.code ?? ""} ${d.name}`.toLowerCase();
      return hay.includes(term);
    });
  }, [items, q]);

  const [open, setOpen] = React.useState(false);
  const [createError, setCreateError] = React.useState<unknown>(null);
  const [requestTypeCode, setRequestTypeCode] = React.useState("");
  const [code, setCode] = React.useState("");
  const [name, setName] = React.useState("");
  const [version, setVersion] = React.useState(1);

  const createM = useMutation({
    mutationFn: async () => {
      const payload: WorkflowDefinitionCreateIn = {
        request_type_code: requestTypeCode.trim(),
        code: code.trim(),
        name: name.trim(),
        version,
        ...(companyId ? { company_id: companyId } : {}),
      };
      if (!payload.request_type_code) throw new Error("Request type code is required.");
      if (!payload.code) throw new Error("Code is required.");
      if (!payload.name) throw new Error("Name is required.");
      if (!payload.version || payload.version < 1) throw new Error("Version must be >= 1.");
      return createDefinition(payload);
    },
    onSuccess: async () => {
      setOpen(false);
      setCreateError(null);
      setRequestTypeCode("");
      setCode("");
      setName("");
      setVersion(1);
      await qc.invalidateQueries({ queryKey: ["workflow", "definitions"] });
    },
    onError: (err) => {
      setCreateError(err);
      toastApiError(err);
    },
  });

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div className="min-w-0">
          <div className="text-lg font-semibold tracking-tight text-text-1">Definitions</div>
          <div className="mt-1 text-sm text-text-2">Routing and approval steps.</div>
        </div>
        <div className="shrink-0">
          <Sheet open={open} onOpenChange={setOpen}>
            <SheetTrigger asChild>
              <Button type="button">Create definition</Button>
            </SheetTrigger>
            <SheetContent className="border-border-subtle bg-surface-2 backdrop-blur-xl">
              <SheetHeader>
                <SheetTitle>Create definition</SheetTitle>
                <SheetDescription>
                  Definitions are create-only in v1. You can update steps after creation.
                </SheetDescription>
              </SheetHeader>

              <div className="space-y-4 px-4">
                {createError ? (
                  <ErrorState title="Create failed" error={createError} variant="inline" className="max-w-none" />
                ) : null}

                <div className="space-y-1">
                  <Label htmlFor="wf-def-type" className="text-xs text-text-2">
                    Request type code
                  </Label>
                  <Input
                    id="wf-def-type"
                    value={requestTypeCode}
                    onChange={(e) => setRequestTypeCode(e.target.value)}
                    placeholder="leave.request"
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="wf-def-code" className="text-xs text-text-2">
                    Code
                  </Label>
                  <Input
                    id="wf-def-code"
                    value={code}
                    onChange={(e) => setCode(e.target.value)}
                    placeholder="LEAVE_DEFAULT"
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="wf-def-name" className="text-xs text-text-2">
                    Name
                  </Label>
                  <Input
                    id="wf-def-name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Default leave approvals"
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="wf-def-version" className="text-xs text-text-2">
                    Version
                  </Label>
                  <Input
                    id="wf-def-version"
                    type="number"
                    value={String(version)}
                    onChange={(e) => setVersion(Number(e.target.value))}
                    min={1}
                  />
                </div>
              </div>

              <SheetFooter>
                <Button type="button" disabled={createM.isPending} onClick={() => createM.mutate()}>
                  {createM.isPending ? "Creating..." : "Create"}
                </Button>
              </SheetFooter>
            </SheetContent>
          </Sheet>
        </div>
      </div>

      <DataTable
        toolbar={
          <FilterBar
            search={{
              value: q,
              onChange: setQ,
              placeholder: "Search definitions...",
              disabled: defsQ.isLoading,
            }}
            rightActions={
              companyId ? (
                <div className="text-xs text-text-3">
                  company: <span className="font-mono">{companyId.slice(0, 8)}…</span>
                </div>
              ) : null
            }
          />
        }
        isLoading={defsQ.isLoading}
        error={defsQ.error}
        onRetry={defsQ.refetch}
        isEmpty={!defsQ.isLoading && !defsQ.error && filtered.length === 0}
        emptyState={
          <EmptyState
            title="No definitions"
            description="Create a workflow definition to start routing requests."
            align="center"
            primaryAction={
              <Button type="button" onClick={() => setOpen(true)}>
                Create definition
              </Button>
            }
          />
        }
        skeleton={{ rows: 6, cols: 5 }}
      >
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Request type</TableHead>
              <TableHead>Version</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Updated</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.map((d) => (
              <TableRow key={d.id}>
                <TableCell className="font-medium">
                  <Link href={`/settings/workflow/definitions/${d.id}`} className="hover:underline">
                    {d.name}
                  </Link>
                  <div className="mt-1 text-xs text-text-3">{d.code ?? d.id.slice(0, 8)}</div>
                </TableCell>
                <TableCell className="text-text-2">{d.request_type_code}</TableCell>
                <TableCell className="text-text-2">{d.version ?? "—"}</TableCell>
                <TableCell>
                  <StatusChip status={d.is_active ? "ACTIVE" : "INACTIVE"} />
                </TableCell>
                <TableCell className="text-text-2">
                  {d.updated_at ? new Date(d.updated_at).toLocaleString() : "—"}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </DataTable>
    </div>
  );
}
