"use client";

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/lib/auth";
import { toastApiError } from "@/lib/toastApiError";
import type { DmsDocumentTypeCreateIn, DmsDocumentTypeOut, DmsDocumentTypePatchIn } from "@/lib/types";
import {
  createDocumentType,
  listDocumentTypes,
  patchDocumentType,
} from "@/features/dms/api/dms";
import { dmsKeys } from "@/features/dms/queryKeys";

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

function TypeForm({
  mode,
  values,
  onChange,
  disabled,
}: {
  mode: "create" | "edit";
  values: { code: string; name: string; requiresExpiry: boolean; isActive: boolean };
  onChange: (next: { code?: string; name?: string; requiresExpiry?: boolean; isActive?: boolean }) => void;
  disabled: boolean;
}) {
  return (
    <div className="space-y-4 px-4">
      <div className="space-y-1">
        <Label htmlFor={`${mode}-doc-type-code`} className="text-xs text-text-2">
          Code
        </Label>
        <Input
          id={`${mode}-doc-type-code`}
          value={values.code}
          onChange={(e) => onChange({ code: e.target.value })}
          placeholder="PASSPORT"
          disabled={disabled || mode === "edit"}
        />
      </div>
      <div className="space-y-1">
        <Label htmlFor={`${mode}-doc-type-name`} className="text-xs text-text-2">
          Name
        </Label>
        <Input
          id={`${mode}-doc-type-name`}
          value={values.name}
          onChange={(e) => onChange({ name: e.target.value })}
          placeholder="Passport"
          disabled={disabled}
        />
      </div>
      <label className="flex items-center gap-3 rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 px-4 py-3 text-sm text-text-1">
        <input
          type="checkbox"
          checked={values.requiresExpiry}
          onChange={(e) => onChange({ requiresExpiry: e.target.checked })}
          disabled={disabled}
          className="h-4 w-4"
        />
        Requires expiry
      </label>
      <label className="flex items-center gap-3 rounded-[var(--ds-radius-16)] border border-border-subtle bg-surface-1 px-4 py-3 text-sm text-text-1">
        <input
          type="checkbox"
          checked={values.isActive}
          onChange={(e) => onChange({ isActive: e.target.checked })}
          disabled={disabled}
          className="h-4 w-4"
        />
        Active
      </label>
    </div>
  );
}

export default function DmsDocumentTypesPage() {
  const qc = useQueryClient();
  const permissions = useAuth((s) => s.permissions);
  const granted = React.useMemo(() => new Set(permissions ?? []), [permissions]);
  const canWrite = granted.has("dms:document-type:write");

  const [q, setQ] = React.useState("");
  const [createOpen, setCreateOpen] = React.useState(false);
  const [createError, setCreateError] = React.useState<unknown>(null);
  const [createValues, setCreateValues] = React.useState({
    code: "",
    name: "",
    requiresExpiry: false,
    isActive: true,
  });

  const [editTarget, setEditTarget] = React.useState<DmsDocumentTypeOut | null>(null);
  const [editError, setEditError] = React.useState<unknown>(null);
  const [editValues, setEditValues] = React.useState({
    code: "",
    name: "",
    requiresExpiry: false,
    isActive: true,
  });

  const typesQ = useQuery({
    queryKey: dmsKeys.documentTypes(),
    queryFn: () => listDocumentTypes(),
  });

  const items = React.useMemo(() => typesQ.data?.items ?? [], [typesQ.data]);
  const filtered = React.useMemo(() => {
    const term = q.trim().toLowerCase();
    if (!term) return items;
    return items.filter((item) => `${item.code} ${item.name}`.toLowerCase().includes(term));
  }, [items, q]);

  const createM = useMutation({
    mutationFn: async () => {
      const payload: DmsDocumentTypeCreateIn = {
        code: createValues.code.trim(),
        name: createValues.name.trim(),
        requires_expiry: createValues.requiresExpiry,
        is_active: createValues.isActive,
      };
      if (!payload.code) throw new Error("Code is required.");
      if (!payload.name) throw new Error("Name is required.");
      return createDocumentType(payload);
    },
    onSuccess: async () => {
      setCreateOpen(false);
      setCreateError(null);
      setCreateValues({ code: "", name: "", requiresExpiry: false, isActive: true });
      await qc.invalidateQueries({ queryKey: dmsKeys.documentTypes() });
    },
    onError: (err) => {
      setCreateError(err);
      toastApiError(err);
    },
  });

  const editM = useMutation({
    mutationFn: async () => {
      if (!editTarget) throw new Error("Select a document type first.");
      const payload: DmsDocumentTypePatchIn = {
        name: editValues.name.trim(),
        requires_expiry: editValues.requiresExpiry,
        is_active: editValues.isActive,
      };
      if (!payload.name) throw new Error("Name is required.");
      return patchDocumentType(editTarget.id, payload);
    },
    onSuccess: async () => {
      setEditTarget(null);
      setEditError(null);
      await qc.invalidateQueries({ queryKey: dmsKeys.documentTypes() });
    },
    onError: (err) => {
      setEditError(err);
      toastApiError(err);
    },
  });

  React.useEffect(() => {
    if (!editTarget) return;
    setEditValues({
      code: editTarget.code,
      name: editTarget.name,
      requiresExpiry: editTarget.requires_expiry,
      isActive: editTarget.is_active,
    });
    setEditError(null);
  }, [editTarget]);

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div className="min-w-0">
          <div className="text-lg font-semibold tracking-tight text-text-1">Document Types</div>
          <div className="mt-1 text-sm text-text-2">Tenant-scoped document catalog for HR and ESS.</div>
        </div>
        <Sheet open={createOpen} onOpenChange={setCreateOpen}>
          <SheetTrigger asChild>
            <Button type="button" disabled={!canWrite}>Create document type</Button>
          </SheetTrigger>
          <SheetContent className="border-border-subtle bg-surface-2 backdrop-blur-xl">
            <SheetHeader>
              <SheetTitle>Create document type</SheetTitle>
              <SheetDescription>Create a tenant document type for employee documents.</SheetDescription>
            </SheetHeader>
            {createError ? (
              <div className="px-4">
                <ErrorState title="Create failed" error={createError} variant="inline" className="max-w-none" />
              </div>
            ) : null}
            <TypeForm
              mode="create"
              values={createValues}
              onChange={(next) => setCreateValues((current) => ({ ...current, ...next }))}
              disabled={!canWrite || createM.isPending}
            />
            <SheetFooter>
              <Button type="button" disabled={!canWrite || createM.isPending} onClick={() => createM.mutate()}>
                {createM.isPending ? "Creating..." : "Create"}
              </Button>
            </SheetFooter>
          </SheetContent>
        </Sheet>
      </div>

      <DataTable
        toolbar={
          <FilterBar
            search={{
              value: q,
              onChange: setQ,
              placeholder: "Search document types...",
              disabled: typesQ.isLoading,
            }}
            onClearAll={q ? () => setQ("") : undefined}
            clearDisabled={typesQ.isLoading}
          />
        }
        isLoading={typesQ.isLoading}
        error={typesQ.error}
        onRetry={typesQ.refetch}
        isEmpty={!typesQ.isLoading && !typesQ.error && filtered.length === 0}
        emptyState={
          <EmptyState
            title="No document types"
            description="Create your first document type to start using DMS."
            align="center"
            primaryAction={
              <Button type="button" disabled={!canWrite} onClick={() => setCreateOpen(true)}>
                Create document type
              </Button>
            }
          />
        }
        skeleton={{ rows: 6, cols: 5 }}
      >
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Code</TableHead>
              <TableHead>Name</TableHead>
              <TableHead>Expiry</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.map((item) => (
              <TableRow key={item.id}>
                <TableCell className="font-medium">{item.code}</TableCell>
                <TableCell className="text-text-1">{item.name}</TableCell>
                <TableCell className="text-text-2">{item.requires_expiry ? "Required" : "Optional"}</TableCell>
                <TableCell>
                  <StatusChip status={item.is_active ? "ACTIVE" : "INACTIVE"} />
                </TableCell>
                <TableCell className="text-right">
                  <Button type="button" variant="outline" disabled={!canWrite} onClick={() => setEditTarget(item)}>
                    Edit
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </DataTable>

      <Sheet open={Boolean(editTarget)} onOpenChange={(open) => !open && setEditTarget(null)}>
        <SheetContent className="border-border-subtle bg-surface-2 backdrop-blur-xl">
          <SheetHeader>
            <SheetTitle>Edit document type</SheetTitle>
            <SheetDescription>Code is immutable after creation.</SheetDescription>
          </SheetHeader>
          {editError ? (
            <div className="px-4">
              <ErrorState title="Update failed" error={editError} variant="inline" className="max-w-none" />
            </div>
          ) : null}
          <TypeForm
            mode="edit"
            values={editValues}
            onChange={(next) => setEditValues((current) => ({ ...current, ...next }))}
            disabled={!canWrite || editM.isPending}
          />
          <SheetFooter>
            <Button type="button" disabled={!canWrite || editM.isPending} onClick={() => editM.mutate()}>
              {editM.isPending ? "Saving..." : "Save"}
            </Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>
    </div>
  );
}
