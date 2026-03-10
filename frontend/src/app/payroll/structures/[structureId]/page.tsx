"use client";

import * as React from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { toast } from "sonner";
import { useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/lib/auth";
import { parseUuidParam } from "@/lib/guards";
import { toastApiError } from "@/lib/toastApiError";
import type {
  PayrollComponentOut,
  SalaryStructureLineCreateIn,
  UUID,
} from "@/lib/types";
import {
  usePayrollComponents,
  useSalaryStructure,
  useSalaryStructureLineCreate,
} from "@/features/payroll/hooks";
import { payrollKeys } from "@/features/payroll/queryKeys";
import { formatPayrollMoney } from "@/features/payroll/utils/format";

import { DataTable } from "@/components/ds/DataTable";
import { DSCard } from "@/components/ds/DSCard";
import { EmptyState } from "@/components/ds/EmptyState";
import { ErrorState } from "@/components/ds/ErrorState";
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const selectClassName = [
  "h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm",
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
].join(" ");

function formatDateTime(value: string): string {
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

export default function PayrollStructureDetailPage({
  params,
}: {
  params: { structureId?: string };
}) {
  const permissions = useAuth((s) => s.permissions);
  const granted = React.useMemo(() => new Set(permissions ?? []), [permissions]);
  const canRead = granted.has("payroll:structure:read");
  const canWrite = granted.has("payroll:structure:write");
  const canReadComponents = granted.has("payroll:component:read");
  const qc = useQueryClient();

  const routeParams = useParams() as { structureId?: string | string[] };
  const structureIdRaw =
    (Array.isArray(routeParams.structureId)
      ? routeParams.structureId[0]
      : routeParams.structureId) ?? params?.structureId ?? null;
  const structureId = parseUuidParam(structureIdRaw) as UUID | null;

  const structureQ = useSalaryStructure(structureId, Boolean(canRead && structureId));
  const componentsQ = usePayrollComponents(null, Boolean(canReadComponents));
  const components = React.useMemo(
    () => ((componentsQ.data ?? []) as PayrollComponentOut[]),
    [componentsQ.data],
  );
  const componentsById = React.useMemo(
    () => new Map(components.map((component) => [component.id, component])),
    [components],
  );

  const [createOpen, setCreateOpen] = React.useState(false);
  const [componentId, setComponentId] = React.useState("");
  const [sortOrder, setSortOrder] = React.useState("");
  const [calcModeOverride, setCalcModeOverride] = React.useState("");
  const [amountOverride, setAmountOverride] = React.useState("");
  const [percentOverride, setPercentOverride] = React.useState("");

  const createLineM = useSalaryStructureLineCreate(structureId ?? ("" as UUID));

  if (!canRead) {
    return (
      <ErrorState
        title="Access denied"
        error={new Error("Your account does not have access to salary structures.")}
      />
    );
  }

  if (!structureIdRaw) {
    return (
      <ErrorState
        title="Missing structure id"
        error={new Error("Open a structure from Payroll Structures.")}
        details={
          <Button asChild variant="secondary">
            <Link href="/payroll/structures">Back to structures</Link>
          </Button>
        }
      />
    );
  }

  if (!structureId) {
    return (
      <ErrorState
        title="Invalid structure id"
        error={new Error(`Got: ${String(structureIdRaw)}`)}
        details={
          <Button asChild variant="secondary">
            <Link href="/payroll/structures">Back to structures</Link>
          </Button>
        }
      />
    );
  }

  const structure = structureQ.data?.structure ?? null;
  const lines = structureQ.data?.lines ?? [];

  async function onCreateLine() {
    if (!structureId) return;
    const parsedSortOrder = Number(sortOrder);
    const payload: SalaryStructureLineCreateIn = {
      component_id: parseUuidParam(componentId) as UUID,
      sort_order: Number.isFinite(parsedSortOrder) ? parsedSortOrder : -1,
      calc_mode_override: calcModeOverride ? (calcModeOverride as SalaryStructureLineCreateIn["calc_mode_override"]) : null,
      amount_override: amountOverride ? amountOverride : null,
      percent_override: percentOverride ? percentOverride : null,
    };

    if (!payload.component_id) {
      toast.error("Select a payroll component.");
      return;
    }
    if (!Number.isInteger(payload.sort_order) || payload.sort_order < 0) {
      toast.error("Sort order must be zero or greater.");
      return;
    }

    try {
      await createLineM.mutateAsync(payload);
      await qc.invalidateQueries({ queryKey: payrollKeys.structure(structureId) });
      setCreateOpen(false);
      setComponentId("");
      setSortOrder("");
      setCalcModeOverride("");
      setAmountOverride("");
      setPercentOverride("");
      toast.success("Structure line added");
    } catch (err) {
      toastApiError(err);
    }
  }

  return (
    <ListRightPanelTemplate
      header={
        <PageHeader
          title={structure ? structure.name : "Salary structure"}
          subtitle={structure ? structure.code : `Structure ${structureId}`}
          actions={
            <div className="flex items-center gap-2">
              {canWrite ? (
                <Sheet open={createOpen} onOpenChange={setCreateOpen}>
                  <SheetTrigger asChild>
                    <Button type="button">Add line</Button>
                  </SheetTrigger>
                  <SheetContent className="border-border-subtle bg-surface-2 backdrop-blur-xl">
                    <SheetHeader>
                      <SheetTitle>Add structure line</SheetTitle>
                      <SheetDescription>
                        Add a payroll component to this structure. Sort order must be unique within the structure.
                      </SheetDescription>
                    </SheetHeader>
                    <div className="space-y-4 px-4">
                      <div className="space-y-1">
                        <Label htmlFor="structure-line-component">Component</Label>
                        {canReadComponents ? (
                          <select
                            id="structure-line-component"
                            className={selectClassName}
                            value={componentId}
                            onChange={(event) => setComponentId(event.target.value)}
                          >
                            <option value="">Select…</option>
                            {components.map((component) => (
                              <option key={component.id} value={component.id}>
                                {component.code} — {component.name}
                              </option>
                            ))}
                          </select>
                        ) : (
                          <Input
                            id="structure-line-component"
                            value={componentId}
                            onChange={(event) => setComponentId(event.target.value)}
                            placeholder="component uuid"
                          />
                        )}
                      </div>
                      <div className="space-y-1">
                        <Label htmlFor="structure-line-sort-order">Sort order</Label>
                        <Input
                          id="structure-line-sort-order"
                          type="number"
                          min={0}
                          value={sortOrder}
                          onChange={(event) => setSortOrder(event.target.value)}
                        />
                      </div>
                      <div className="space-y-1">
                        <Label htmlFor="structure-line-calc-mode">Calc mode override</Label>
                        <select
                          id="structure-line-calc-mode"
                          className={selectClassName}
                          value={calcModeOverride}
                          onChange={(event) => setCalcModeOverride(event.target.value)}
                        >
                          <option value="">Default</option>
                          <option value="FIXED">Fixed</option>
                          <option value="PERCENT_OF_GROSS">Percent of gross</option>
                          <option value="MANUAL">Manual</option>
                        </select>
                      </div>
                      <div className="grid gap-4 md:grid-cols-2">
                        <div className="space-y-1">
                          <Label htmlFor="structure-line-amount">Amount override</Label>
                          <Input
                            id="structure-line-amount"
                            value={amountOverride}
                            onChange={(event) => setAmountOverride(event.target.value)}
                            placeholder="0.00"
                          />
                        </div>
                        <div className="space-y-1">
                          <Label htmlFor="structure-line-percent">Percent override</Label>
                          <Input
                            id="structure-line-percent"
                            value={percentOverride}
                            onChange={(event) => setPercentOverride(event.target.value)}
                            placeholder="0"
                          />
                        </div>
                      </div>
                    </div>
                    <SheetFooter>
                      <Button
                        type="button"
                        disabled={createLineM.isPending}
                        onClick={() => void onCreateLine()}
                      >
                        {createLineM.isPending ? "Saving..." : "Add line"}
                      </Button>
                    </SheetFooter>
                  </SheetContent>
                </Sheet>
              ) : null}
              <Button asChild type="button" variant="secondary">
                <Link href="/payroll/structures">Back</Link>
              </Button>
            </div>
          }
        />
      }
      main={
        <DataTable
          isLoading={structureQ.isLoading}
          error={structureQ.error}
          onRetry={() => void structureQ.refetch()}
          isEmpty={!structureQ.isLoading && !structureQ.error && lines.length === 0}
          emptyState={
            <EmptyState
              title="No structure lines"
              description="Add payroll component lines to define the structure calculation order."
              align="center"
            />
          }
          skeleton={{ rows: 6, cols: 5 }}
        >
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Sort</TableHead>
                <TableHead>Component</TableHead>
                <TableHead>Mode</TableHead>
                <TableHead>Amount override</TableHead>
                <TableHead>Percent override</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {lines.map((line) => {
                const component = componentsById.get(line.component_id);
                return (
                  <TableRow key={line.id}>
                    <TableCell className="font-medium">{line.sort_order}</TableCell>
                    <TableCell>
                      <div className="text-text-1">{component?.name ?? line.component_id}</div>
                      <div className="mt-1 text-xs text-text-3">{component?.code ?? "Component"}</div>
                    </TableCell>
                    <TableCell>{line.calc_mode_override ?? "Default"}</TableCell>
                    <TableCell>{formatPayrollMoney(line.amount_override, structure ? "SAR" : "SAR")}</TableCell>
                    <TableCell>{line.percent_override ?? "—"}</TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </DataTable>
      }
      right={
        <RightPanelStack>
          <DSCard surface="panel" className="space-y-4 p-[var(--ds-space-16)]">
            <div>
              <div className="text-sm font-semibold tracking-tight text-text-1">Structure summary</div>
              {structure ? (
                <div className="mt-1 text-sm text-text-2">
                  {structure.name} ({structure.code})
                </div>
              ) : (
                <div className="mt-1 text-sm text-text-2">Loading structure metadata…</div>
              )}
            </div>
            {structure ? (
              <>
                <div className="flex flex-wrap gap-2">
                  <StatusChip status={structure.is_active ? "ACTIVE" : "INACTIVE"} />
                </div>
                <div className="space-y-2 text-sm text-text-2">
                  <div>Lines: {lines.length}</div>
                  <div>Created: {formatDateTime(structure.created_at)}</div>
                  <div>Updated: {formatDateTime(structure.updated_at)}</div>
                </div>
              </>
            ) : null}
          </DSCard>

          <DSCard surface="panel" className="space-y-3 p-[var(--ds-space-16)]">
            <div className="text-sm font-semibold tracking-tight text-text-1">Supported in v1</div>
            <div className="text-sm text-text-2">
              Salary structures support create, detail, and line-add. There is no browse, edit, or delete endpoint in the current backend.
            </div>
          </DSCard>
        </RightPanelStack>
      }
    />
  );
}
