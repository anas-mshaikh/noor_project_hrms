"use client";

import * as React from "react";
import { toast } from "sonner";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/lib/auth";
import { parseUuidParam } from "@/lib/guards";
import { useSelection } from "@/lib/selection";
import { toastApiError } from "@/lib/toastApiError";
import type { ShiftTemplateCreateIn, ShiftTemplateOut, ShiftTemplatePatchIn } from "@/lib/types";
import { createShiftTemplate, listShiftTemplates, patchShiftTemplate } from "@/features/roster/api/roster";
import { rosterKeys } from "@/features/roster/queryKeys";
import { BranchScopeState } from "@/features/roster/components";

import { DataTable } from "@/components/ds/DataTable";
import { DSCard } from "@/components/ds/DSCard";
import { EmptyState } from "@/components/ds/EmptyState";
import { ErrorState } from "@/components/ds/ErrorState";
import { FilterBar } from "@/components/ds/FilterBar";
import { PageHeader } from "@/components/ds/PageHeader";
import { RightPanelStack } from "@/components/ds/RightPanelStack";
import { StatusChip } from "@/components/ds/StatusChip";
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
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

function timeValue(value: string | null | undefined): string {
  return value ? value.slice(0, 5) : "";
}

function buildShiftPayload(args: {
  code: string;
  name: string;
  startTime: string;
  endTime: string;
  breakMinutes: string;
  graceMinutes: string;
  minFullDayMinutes: string;
  isActive: boolean;
}): ShiftTemplateCreateIn {
  if (!args.code.trim()) throw new Error("Code is required.");
  if (!args.name.trim()) throw new Error("Name is required.");
  if (!args.startTime) throw new Error("Start time is required.");
  if (!args.endTime) throw new Error("End time is required.");
  return {
    code: args.code.trim(),
    name: args.name.trim(),
    start_time: args.startTime,
    end_time: args.endTime,
    break_minutes: args.breakMinutes ? Number(args.breakMinutes) : 0,
    grace_minutes: args.graceMinutes ? Number(args.graceMinutes) : 0,
    min_full_day_minutes: args.minFullDayMinutes ? Number(args.minFullDayMinutes) : null,
    is_active: args.isActive,
  };
}

function buildShiftPatchPayload(args: {
  code: string;
  name: string;
  startTime: string;
  endTime: string;
  breakMinutes: string;
  graceMinutes: string;
  minFullDayMinutes: string;
  isActive: boolean;
}): ShiftTemplatePatchIn {
  return buildShiftPayload(args);
}

export default function RosterShiftsPage() {
  const permissions = useAuth((s) => s.permissions);
  const permSet = React.useMemo(() => new Set(permissions ?? []), [permissions]);
  const canRead = permSet.has("roster:shift:read");
  const canWrite = permSet.has("roster:shift:write");

  const branchId = parseUuidParam(useSelection((s) => s.branchId));
  const qc = useQueryClient();

  const [activeOnly, setActiveOnly] = React.useState(true);
  const shiftsQ = useQuery({
    queryKey: rosterKeys.shifts({ branchId, activeOnly }),
    enabled: Boolean(branchId && canRead),
    queryFn: () => listShiftTemplates({ branchId: branchId as ShiftTemplateOut["branch_id"], activeOnly }),
  });

  const shifts = React.useMemo(
    () => (shiftsQ.data ?? []) as ShiftTemplateOut[],
    [shiftsQ.data],
  );
  const [selectedId, setSelectedId] = React.useState<string | null>(null);
  const selected = React.useMemo(
    () => (selectedId ? shifts.find((shift) => shift.id === selectedId) ?? null : shifts[0] ?? null),
    [selectedId, shifts],
  );

  React.useEffect(() => {
    if (!selectedId && shifts[0]) setSelectedId(shifts[0].id);
  }, [selectedId, shifts]);

  const [createOpen, setCreateOpen] = React.useState(false);
  const [createCode, setCreateCode] = React.useState("");
  const [createName, setCreateName] = React.useState("");
  const [createStart, setCreateStart] = React.useState("09:00");
  const [createEnd, setCreateEnd] = React.useState("18:00");
  const [createBreak, setCreateBreak] = React.useState("60");
  const [createGrace, setCreateGrace] = React.useState("10");
  const [createMinMinutes, setCreateMinMinutes] = React.useState("480");
  const [createActive, setCreateActive] = React.useState(true);

  const createM = useMutation({
    mutationFn: async () => {
      if (!branchId) throw new Error("Select a branch first.");
      return createShiftTemplate(
        branchId,
        buildShiftPayload({
          code: createCode,
          name: createName,
          startTime: createStart,
          endTime: createEnd,
          breakMinutes: createBreak,
          graceMinutes: createGrace,
          minFullDayMinutes: createMinMinutes,
          isActive: createActive,
        }),
      );
    },
    onSuccess: async (shift) => {
      setCreateOpen(false);
      setCreateCode("");
      setCreateName("");
      setCreateStart("09:00");
      setCreateEnd("18:00");
      setCreateBreak("60");
      setCreateGrace("10");
      setCreateMinMinutes("480");
      setCreateActive(true);
      setSelectedId(shift.id);
      await qc.invalidateQueries({ queryKey: ["roster", "shifts"] });
      toast.success("Shift template created");
    },
    onError: (err) => toastApiError(err),
  });

  const [editOpen, setEditOpen] = React.useState(false);
  const [editCode, setEditCode] = React.useState("");
  const [editName, setEditName] = React.useState("");
  const [editStart, setEditStart] = React.useState("");
  const [editEnd, setEditEnd] = React.useState("");
  const [editBreak, setEditBreak] = React.useState("0");
  const [editGrace, setEditGrace] = React.useState("0");
  const [editMinMinutes, setEditMinMinutes] = React.useState("");
  const [editActive, setEditActive] = React.useState(true);

  React.useEffect(() => {
    if (!editOpen || !selected) return;
    setEditCode(selected.code);
    setEditName(selected.name);
    setEditStart(timeValue(selected.start_time));
    setEditEnd(timeValue(selected.end_time));
    setEditBreak(String(selected.break_minutes));
    setEditGrace(String(selected.grace_minutes));
    setEditMinMinutes(selected.min_full_day_minutes == null ? "" : String(selected.min_full_day_minutes));
    setEditActive(selected.is_active);
  }, [editOpen, selected]);

  const editM = useMutation({
    mutationFn: async () => {
      if (!selected) throw new Error("Select a shift first.");
      return patchShiftTemplate(
        selected.id,
        buildShiftPatchPayload({
          code: editCode,
          name: editName,
          startTime: editStart,
          endTime: editEnd,
          breakMinutes: editBreak,
          graceMinutes: editGrace,
          minFullDayMinutes: editMinMinutes,
          isActive: editActive,
        }),
      );
    },
    onSuccess: async () => {
      setEditOpen(false);
      await qc.invalidateQueries({ queryKey: ["roster", "shifts"] });
      toast.success("Shift template updated");
    },
    onError: (err) => toastApiError(err),
  });

  if (!canRead) {
    return (
      <ErrorState title="Access denied" error={new Error("Your account does not have access to shift templates.")} />
    );
  }

  if (!branchId) {
    return <BranchScopeState />;
  }

  const right = selected ? (
    <RightPanelStack>
      <DSCard surface="panel" className="space-y-4 p-[var(--ds-space-16)]">
        <div>
          <div className="text-sm font-medium text-text-1">{selected.name}</div>
          <div className="mt-1 text-sm text-text-2">{selected.code}</div>
        </div>
        <div className="flex flex-wrap gap-2">
          <StatusChip status={selected.is_active ? "ACTIVE" : "INACTIVE"} />
          <div className="rounded-full border border-border-subtle bg-surface-1 px-3 py-1 text-xs text-text-2">
            {timeValue(selected.start_time)} - {timeValue(selected.end_time)}
          </div>
        </div>
        <div className="grid gap-3 text-sm sm:grid-cols-2">
          <div>
            <div className="text-xs text-text-3">Expected minutes</div>
            <div className="font-medium text-text-1">{selected.expected_minutes}</div>
          </div>
          <div>
            <div className="text-xs text-text-3">Break minutes</div>
            <div className="font-medium text-text-1">{selected.break_minutes}</div>
          </div>
          <div>
            <div className="text-xs text-text-3">Grace minutes</div>
            <div className="font-medium text-text-1">{selected.grace_minutes}</div>
          </div>
          <div>
            <div className="text-xs text-text-3">Min full day</div>
            <div className="font-medium text-text-1">{selected.min_full_day_minutes ?? "-"}</div>
          </div>
        </div>
        {canWrite ? (
          <Sheet open={editOpen} onOpenChange={setEditOpen}>
            <SheetTrigger asChild>
              <Button type="button" variant="secondary">Edit shift</Button>
            </SheetTrigger>
            <SheetContent className="border-border-subtle bg-surface-2 backdrop-blur-xl">
              <SheetHeader>
                <SheetTitle>Edit shift template</SheetTitle>
                <SheetDescription>Update shift timing and roster rules.</SheetDescription>
              </SheetHeader>
              <div className="space-y-4 px-4 text-sm">
                <div className="space-y-1"><Label htmlFor="edit-shift-code">Code</Label><Input id="edit-shift-code" value={editCode} onChange={(e) => setEditCode(e.target.value)} disabled={editM.isPending} /></div>
                <div className="space-y-1"><Label htmlFor="edit-shift-name">Name</Label><Input id="edit-shift-name" value={editName} onChange={(e) => setEditName(e.target.value)} disabled={editM.isPending} /></div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-1"><Label htmlFor="edit-shift-start">Start time</Label><Input id="edit-shift-start" type="time" value={editStart} onChange={(e) => setEditStart(e.target.value)} disabled={editM.isPending} /></div>
                  <div className="space-y-1"><Label htmlFor="edit-shift-end">End time</Label><Input id="edit-shift-end" type="time" value={editEnd} onChange={(e) => setEditEnd(e.target.value)} disabled={editM.isPending} /></div>
                </div>
                <div className="grid gap-4 sm:grid-cols-3">
                  <div className="space-y-1"><Label htmlFor="edit-shift-break">Break minutes</Label><Input id="edit-shift-break" type="number" min="0" value={editBreak} onChange={(e) => setEditBreak(e.target.value)} disabled={editM.isPending} /></div>
                  <div className="space-y-1"><Label htmlFor="edit-shift-grace">Grace minutes</Label><Input id="edit-shift-grace" type="number" min="0" value={editGrace} onChange={(e) => setEditGrace(e.target.value)} disabled={editM.isPending} /></div>
                  <div className="space-y-1"><Label htmlFor="edit-shift-minutes">Min full day minutes</Label><Input id="edit-shift-minutes" type="number" min="0" value={editMinMinutes} onChange={(e) => setEditMinMinutes(e.target.value)} disabled={editM.isPending} /></div>
                </div>
                <label className="flex items-center gap-2 text-sm text-text-1">
                  <input type="checkbox" checked={editActive} onChange={(e) => setEditActive(e.target.checked)} disabled={editM.isPending} />
                  Active
                </label>
              </div>
              <SheetFooter>
                <Button type="button" variant="secondary" onClick={() => setEditOpen(false)} disabled={editM.isPending}>Cancel</Button>
                <Button type="button" onClick={() => editM.mutate()} disabled={editM.isPending}>{editM.isPending ? "Saving..." : "Save changes"}</Button>
              </SheetFooter>
            </SheetContent>
          </Sheet>
        ) : null}
      </DSCard>
    </RightPanelStack>
  ) : (
    <DSCard surface="panel" className="p-[var(--ds-space-16)]">
      <EmptyState title="Select a shift" description="Pick a shift template to review its settings." align="center" />
    </DSCard>
  );

  return (
    <ListRightPanelTemplate
      header={
        <PageHeader
          title="Shift Templates"
          subtitle="Create and maintain branch shift templates."
          actions={
            canWrite ? (
              <Sheet open={createOpen} onOpenChange={setCreateOpen}>
                <SheetTrigger asChild>
                  <Button type="button">Create shift</Button>
                </SheetTrigger>
                <SheetContent className="border-border-subtle bg-surface-2 backdrop-blur-xl">
                  <SheetHeader>
                    <SheetTitle>Create shift template</SheetTitle>
                    <SheetDescription>Define working hours, breaks, and grace rules.</SheetDescription>
                  </SheetHeader>
                  <div className="space-y-4 px-4 text-sm">
                    <div className="space-y-1"><Label htmlFor="create-shift-code">Code</Label><Input id="create-shift-code" value={createCode} onChange={(e) => setCreateCode(e.target.value)} disabled={createM.isPending} /></div>
                    <div className="space-y-1"><Label htmlFor="create-shift-name">Name</Label><Input id="create-shift-name" value={createName} onChange={(e) => setCreateName(e.target.value)} disabled={createM.isPending} /></div>
                    <div className="grid gap-4 sm:grid-cols-2">
                      <div className="space-y-1"><Label htmlFor="create-shift-start">Start time</Label><Input id="create-shift-start" type="time" value={createStart} onChange={(e) => setCreateStart(e.target.value)} disabled={createM.isPending} /></div>
                      <div className="space-y-1"><Label htmlFor="create-shift-end">End time</Label><Input id="create-shift-end" type="time" value={createEnd} onChange={(e) => setCreateEnd(e.target.value)} disabled={createM.isPending} /></div>
                    </div>
                    <div className="grid gap-4 sm:grid-cols-3">
                      <div className="space-y-1"><Label htmlFor="create-shift-break">Break minutes</Label><Input id="create-shift-break" type="number" min="0" value={createBreak} onChange={(e) => setCreateBreak(e.target.value)} disabled={createM.isPending} /></div>
                      <div className="space-y-1"><Label htmlFor="create-shift-grace">Grace minutes</Label><Input id="create-shift-grace" type="number" min="0" value={createGrace} onChange={(e) => setCreateGrace(e.target.value)} disabled={createM.isPending} /></div>
                      <div className="space-y-1"><Label htmlFor="create-shift-minutes">Min full day minutes</Label><Input id="create-shift-minutes" type="number" min="0" value={createMinMinutes} onChange={(e) => setCreateMinMinutes(e.target.value)} disabled={createM.isPending} /></div>
                    </div>
                    <label className="flex items-center gap-2 text-sm text-text-1">
                      <input type="checkbox" checked={createActive} onChange={(e) => setCreateActive(e.target.checked)} disabled={createM.isPending} />
                      Active
                    </label>
                  </div>
                  <SheetFooter>
                    <Button type="button" variant="secondary" onClick={() => setCreateOpen(false)} disabled={createM.isPending}>Cancel</Button>
                    <Button type="button" onClick={() => createM.mutate()} disabled={createM.isPending}>{createM.isPending ? "Saving..." : "Create shift"}</Button>
                  </SheetFooter>
                </SheetContent>
              </Sheet>
            ) : null
          }
        />
      }
      main={
        <DataTable
          toolbar={
            <FilterBar
              chips={
                <label className="inline-flex items-center gap-2 rounded-full border border-border-subtle bg-background px-3 py-1 text-xs text-text-2">
                  <input type="checkbox" checked={activeOnly} onChange={(e) => setActiveOnly(e.target.checked)} />
                  Active only
                </label>
              }
            />
          }
          isLoading={shiftsQ.isLoading}
          error={shiftsQ.error}
          onRetry={shiftsQ.refetch}
          isEmpty={!shiftsQ.isLoading && !shiftsQ.error && shifts.length === 0}
          emptyState={
            <EmptyState
              title="No shift templates"
              description="Create the first shift template for this branch."
              primaryAction={canWrite ? <Button type="button" onClick={() => setCreateOpen(true)}>Create shift</Button> : undefined}
              align="center"
            />
          }
          skeleton={{ rows: 6, cols: 5 }}
        >
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Shift</TableHead>
                <TableHead>Hours</TableHead>
                <TableHead>Expected</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {shifts.map((shift) => (
                <TableRow
                  key={shift.id}
                  data-state={selected?.id === shift.id ? "selected" : undefined}
                  className="cursor-pointer"
                  onClick={() => setSelectedId(shift.id)}
                >
                  <TableCell>
                    <div className="font-medium text-text-1">{shift.name}</div>
                    <div className="text-xs text-text-3">{shift.code}</div>
                  </TableCell>
                  <TableCell>{timeValue(shift.start_time)} - {timeValue(shift.end_time)}</TableCell>
                  <TableCell>{shift.expected_minutes} min</TableCell>
                  <TableCell><StatusChip status={shift.is_active ? "ACTIVE" : "INACTIVE"} /></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </DataTable>
      }
      right={right}
    />
  );
}
