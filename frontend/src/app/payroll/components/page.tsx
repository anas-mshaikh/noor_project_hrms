"use client";

import * as React from "react";
import { toast } from "sonner";
import { useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/lib/auth";
import { toastApiError } from "@/lib/toastApiError";
import type { PayrollComponentCreateIn } from "@/lib/types";
import { usePayrollComponentCreate, usePayrollComponents } from "@/features/payroll/hooks";
import { payrollKeys } from "@/features/payroll/queryKeys";
import { formatPayrollMoney } from "@/features/payroll/utils/format";

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
import { Sheet, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

export default function PayrollComponentsPage() {
  const user = useAuth((s) => s.user);
  const permissions = useAuth((s) => s.permissions);
  const granted = React.useMemo(() => new Set(permissions ?? []), [permissions]);
  const canRead = granted.has("payroll:component:read");
  const canWrite = granted.has("payroll:component:write");
  const qc = useQueryClient();

  const [type, setType] = React.useState<string>("");
  const [selectedId, setSelectedId] = React.useState<string | null>(null);
  const componentsQ = usePayrollComponents(type || null, Boolean(user && canRead));
  const components = React.useMemo(() => componentsQ.data ?? [], [componentsQ.data]);
  const selected = React.useMemo(
    () => (selectedId ? components.find((component) => component.id === selectedId) ?? null : components[0] ?? null),
    [components, selectedId],
  );
  React.useEffect(() => {
    if (!selectedId && components[0]) setSelectedId(components[0].id);
  }, [components, selectedId]);

  const [createOpen, setCreateOpen] = React.useState(false);
  const [code, setCode] = React.useState("");
  const [name, setName] = React.useState("");
  const [componentType, setComponentType] = React.useState<"EARNING" | "DEDUCTION">("EARNING");
  const [calcMode, setCalcMode] = React.useState<"FIXED" | "PERCENT_OF_GROSS" | "MANUAL">("FIXED");
  const [defaultAmount, setDefaultAmount] = React.useState("");
  const [defaultPercent, setDefaultPercent] = React.useState("");
  const [isTaxable, setIsTaxable] = React.useState(false);
  const [isActive, setIsActive] = React.useState(true);
  const createM = usePayrollComponentCreate();

  if (!user) {
    return <ErrorState title="Sign in required" error={new Error("Please sign in to manage payroll components.")} />;
  }

  if (!canRead) {
    return <ErrorState title="Access denied" error={new Error("Your account does not have access to payroll components.")} />;
  }

  async function onCreate() {
    const payload: PayrollComponentCreateIn = {
      code: code.trim(),
      name: name.trim(),
      component_type: componentType,
      calc_mode: calcMode,
      default_amount: defaultAmount ? defaultAmount : null,
      default_percent: defaultPercent ? defaultPercent : null,
      is_taxable: isTaxable,
      is_active: isActive,
    };
    if (!payload.code || !payload.name) {
      toast.error("Code and name are required.");
      return;
    }
    try {
      const created = await createM.mutateAsync(payload);
      await qc.invalidateQueries({ queryKey: payrollKeys.components(type || null) });
      setSelectedId(created.id);
      setCreateOpen(false);
      setCode("");
      setName("");
      setComponentType("EARNING");
      setCalcMode("FIXED");
      setDefaultAmount("");
      setDefaultPercent("");
      setIsTaxable(false);
      setIsActive(true);
      toast.success("Payroll component created");
    } catch (err) {
      toastApiError(err);
    }
  }

  return (
    <ListRightPanelTemplate
      header={
        <PageHeader
          title="Payroll components"
          subtitle="Tenant-wide earnings and deductions used in salary structures."
          actions={
            canWrite ? (
              <Sheet open={createOpen} onOpenChange={setCreateOpen}>
                <SheetTrigger asChild>
                  <Button type="button">Create component</Button>
                </SheetTrigger>
                <SheetContent className="border-border-subtle bg-surface-2 backdrop-blur-xl">
                  <SheetHeader>
                    <SheetTitle>Create payroll component</SheetTitle>
                    <SheetDescription>Components are catalog items used inside salary structures.</SheetDescription>
                  </SheetHeader>
                  <div className="space-y-4 px-4">
                    <div className="space-y-1"><Label htmlFor="component-code">Code</Label><Input id="component-code" value={code} onChange={(e) => setCode(e.target.value)} /></div>
                    <div className="space-y-1"><Label htmlFor="component-name">Name</Label><Input id="component-name" value={name} onChange={(e) => setName(e.target.value)} /></div>
                    <div className="space-y-1"><Label htmlFor="component-type">Type</Label><select id="component-type" className="h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm" value={componentType} onChange={(e) => setComponentType(e.target.value as typeof componentType)}><option value="EARNING">Earning</option><option value="DEDUCTION">Deduction</option></select></div>
                    <div className="space-y-1"><Label htmlFor="component-calc-mode">Calculation mode</Label><select id="component-calc-mode" className="h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm" value={calcMode} onChange={(e) => setCalcMode(e.target.value as typeof calcMode)}><option value="FIXED">Fixed</option><option value="PERCENT_OF_GROSS">Percent of gross</option><option value="MANUAL">Manual</option></select></div>
                    <div className="space-y-1"><Label htmlFor="component-default-amount">Default amount</Label><Input id="component-default-amount" value={defaultAmount} onChange={(e) => setDefaultAmount(e.target.value)} placeholder="0.00" /></div>
                    <div className="space-y-1"><Label htmlFor="component-default-percent">Default percent</Label><Input id="component-default-percent" value={defaultPercent} onChange={(e) => setDefaultPercent(e.target.value)} placeholder="0" /></div>
                    <label className="flex items-center gap-2 text-sm text-text-2"><input type="checkbox" checked={isTaxable} onChange={(e) => setIsTaxable(e.target.checked)} /> Taxable</label>
                    <label className="flex items-center gap-2 text-sm text-text-2"><input type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} /> Active</label>
                  </div>
                  <SheetFooter>
                    <Button type="button" disabled={createM.isPending} onClick={() => void onCreate()}>
                      {createM.isPending ? "Creating..." : "Create component"}
                    </Button>
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
                <select
                  aria-label="Component type"
                  className="h-9 rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm"
                  value={type}
                  onChange={(e) => setType(e.target.value)}
                >
                  <option value="">All types</option>
                  <option value="EARNING">Earning</option>
                  <option value="DEDUCTION">Deduction</option>
                </select>
              }
              onClearAll={type ? () => setType("") : undefined}
            />
          }
          isLoading={componentsQ.isLoading}
          error={componentsQ.error}
          onRetry={() => void componentsQ.refetch()}
          isEmpty={!componentsQ.isLoading && !componentsQ.error && components.length === 0}
          emptyState={<EmptyState title="No payroll components" description="Create an earning or deduction component to continue." align="center" />}
          skeleton={{ rows: 6, cols: 4 }}
        >
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Code</TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Mode</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {components.map((component) => (
                <TableRow key={component.id} className="cursor-pointer" onClick={() => setSelectedId(component.id)}>
                  <TableCell className="font-medium">{component.code}</TableCell>
                  <TableCell>{component.name}</TableCell>
                  <TableCell>{component.component_type}</TableCell>
                  <TableCell>{component.calc_mode}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </DataTable>
      }
      right={
        <RightPanelStack>
          <DSCard surface="panel" className="space-y-3 p-[var(--ds-space-16)]">
            <div className="text-sm font-semibold tracking-tight text-text-1">Selected component</div>
            {selected ? (
              <>
                <div className="text-sm text-text-1">{selected.name}</div>
                <div className="text-sm text-text-2">{selected.code}</div>
                <div className="flex flex-wrap gap-2">
                  <StatusChip status={selected.component_type} />
                  <StatusChip status={selected.is_active ? "ACTIVE" : "INACTIVE"} />
                </div>
                <div className="space-y-2 text-sm text-text-2">
                  <div>Calc mode: {selected.calc_mode}</div>
                  <div>Default amount: {formatPayrollMoney(selected.default_amount, "SAR")}</div>
                  <div>Default percent: {selected.default_percent ?? "—"}</div>
                  <div>Taxable: {selected.is_taxable ? "Yes" : "No"}</div>
                </div>
              </>
            ) : (
              <EmptyState title="Select a component" description="Component details are shown here." align="center" />
            )}
          </DSCard>
        </RightPanelStack>
      }
    />
  );
}
