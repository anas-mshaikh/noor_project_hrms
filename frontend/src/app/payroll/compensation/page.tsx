"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/lib/auth";
import { parseUuidParam } from "@/lib/guards";
import { useSelection } from "@/lib/selection";
import { toastApiError } from "@/lib/toastApiError";
import type {
  EmployeeCompensationUpsertIn,
  EmployeeDirectoryRowOut,
  UUID,
} from "@/lib/types";
import { getEmployee, listEmployees } from "@/features/hr-core/api/hrCore";
import { hrCoreKeys } from "@/features/hr-core/queryKeys";
import {
  useEmployeeCompensation,
  useEmployeeCompensationUpsert,
  useSalaryStructure,
} from "@/features/payroll/hooks";
import { PayrollScopeState } from "@/features/payroll/components/PayrollScopeState";
import { payrollKeys } from "@/features/payroll/queryKeys";
import { formatPayrollMoney } from "@/features/payroll/utils/format";
import { EmployeePickerCard } from "@/features/roster/components";

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

function formatDate(value: string | null): string {
  return value ?? "—";
}

function formatDateTime(value: string): string {
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

function compensationHref(args: {
  employeeId?: UUID | null;
  structureId?: UUID | null;
}): string {
  const params = new URLSearchParams();
  if (args.employeeId) params.set("employeeId", args.employeeId);
  if (args.structureId) params.set("structureId", args.structureId);
  const qs = params.toString();
  return qs ? `/payroll/compensation?${qs}` : "/payroll/compensation";
}

export default function PayrollCompensationPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const qc = useQueryClient();

  const permissions = useAuth((s) => s.permissions);
  const granted = React.useMemo(() => new Set(permissions ?? []), [permissions]);
  const canRead = granted.has("payroll:compensation:read");
  const canWrite = granted.has("payroll:compensation:write");
  const canReadStructures = granted.has("payroll:structure:read");

  const companyId = parseUuidParam(useSelection((s) => s.companyId));
  const branchId = parseUuidParam(useSelection((s) => s.branchId));

  const employeeId = parseUuidParam(searchParams.get("employeeId"));
  const structureIdPrefill = parseUuidParam(searchParams.get("structureId"));

  const [employeeSearch, setEmployeeSearch] = React.useState("");
  const employeesQ = useQuery({
    queryKey: hrCoreKeys.employees({
      companyId,
      q: employeeSearch.trim() ? employeeSearch.trim() : null,
      status: null,
      branchId,
      orgUnitId: null,
      limit: 8,
      offset: 0,
    }),
    enabled: Boolean(companyId && canRead),
    queryFn: () =>
      listEmployees({
        companyId: companyId as UUID,
        branchId,
        q: employeeSearch.trim() ? employeeSearch.trim() : null,
        limit: 8,
        offset: 0,
      }),
  });

  const employeeQ = useQuery({
    queryKey: hrCoreKeys.employee({ companyId, employeeId }),
    enabled: Boolean(companyId && employeeId && canRead),
    queryFn: () => getEmployee({ companyId: companyId as UUID, employeeId: employeeId as UUID }),
  });

  const compensationQ = useEmployeeCompensation(employeeId, Boolean(employeeId && canRead));
  const structureQ = useSalaryStructure(
    structureIdPrefill,
    Boolean(structureIdPrefill && canReadStructures),
  );

  const employees = (employeesQ.data?.items ?? []) as EmployeeDirectoryRowOut[];
  const employee = employeeQ.data ?? null;
  const compensation = compensationQ.data ?? [];

  const [createOpen, setCreateOpen] = React.useState(false);
  const [currencyCode, setCurrencyCode] = React.useState("SAR");
  const [salaryStructureId, setSalaryStructureId] = React.useState(structureIdPrefill ?? "");
  const [baseAmount, setBaseAmount] = React.useState("");
  const [effectiveFrom, setEffectiveFrom] = React.useState("");
  const [effectiveTo, setEffectiveTo] = React.useState("");
  const [overridesJson, setOverridesJson] = React.useState("");

  React.useEffect(() => {
    if (structureIdPrefill) setSalaryStructureId(structureIdPrefill);
  }, [structureIdPrefill]);

  const createM = useEmployeeCompensationUpsert(employeeId ?? ("" as UUID));

  if (!canRead) {
    return (
      <ErrorState
        title="Access denied"
        error={new Error("Your account does not have access to compensation records.")}
      />
    );
  }

  if (!companyId) {
    return (
      <PayrollScopeState
        title="Select a company"
        description="Employee compensation is company-scoped. Select a company first to choose an employee."
      />
    );
  }

  function setEmployee(nextEmployeeId: UUID) {
    router.push(
      compensationHref({ employeeId: nextEmployeeId, structureId: structureIdPrefill }),
    );
  }

  async function onCreate() {
    if (!employeeId) {
      toast.error("Select an employee first.");
      return;
    }
    const parsedStructureId = parseUuidParam(salaryStructureId);
    if (!parsedStructureId) {
      toast.error("Enter a valid salary structure UUID.");
      return;
    }

    let overrides: Record<string, unknown> | null = null;
    if (overridesJson.trim()) {
      try {
        const parsed = JSON.parse(overridesJson) as unknown;
        if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
          toast.error("Overrides JSON must be an object.");
          return;
        }
        overrides = parsed as Record<string, unknown>;
      } catch {
        toast.error("Overrides JSON is not valid JSON.");
        return;
      }
    }

    const payload: EmployeeCompensationUpsertIn = {
      currency_code: currencyCode.trim(),
      salary_structure_id: parsedStructureId,
      base_amount: baseAmount.trim(),
      effective_from: effectiveFrom,
      effective_to: effectiveTo || null,
      overrides_json: overrides,
    };

    if (!payload.currency_code || !payload.base_amount || !payload.effective_from) {
      toast.error("Currency, base amount, and effective from are required.");
      return;
    }

    try {
      await createM.mutateAsync(payload);
      await qc.invalidateQueries({ queryKey: payrollKeys.employeeCompensation(employeeId) });
      setCreateOpen(false);
      setBaseAmount("");
      setEffectiveFrom("");
      setEffectiveTo("");
      setOverridesJson("");
      toast.success("Compensation record added");
    } catch (err) {
      toastApiError(err);
    }
  }

  return (
    <ListRightPanelTemplate
      header={
        <PageHeader
          title="Employee compensation"
          subtitle="Effective-dated compensation records by employee."
          actions={
            employeeId && canWrite ? (
              <Sheet open={createOpen} onOpenChange={setCreateOpen}>
                <SheetTrigger asChild>
                  <Button type="button">Add compensation record</Button>
                </SheetTrigger>
                <SheetContent className="border-border-subtle bg-surface-2 backdrop-blur-xl">
                  <SheetHeader>
                    <SheetTitle>Add compensation record</SheetTitle>
                    <SheetDescription>
                      Compensation is additive in v1. Overlap conflicts are rejected by the backend.
                    </SheetDescription>
                  </SheetHeader>
                  <div className="space-y-4 px-4">
                    <div className="space-y-1">
                      <Label htmlFor="comp-currency">Currency</Label>
                      <Input
                        id="comp-currency"
                        value={currencyCode}
                        onChange={(event) => setCurrencyCode(event.target.value)}
                      />
                    </div>
                    <div className="space-y-1">
                      <Label htmlFor="comp-structure">Salary structure UUID</Label>
                      <Input
                        id="comp-structure"
                        value={salaryStructureId}
                        onChange={(event) => setSalaryStructureId(event.target.value)}
                        placeholder="xxxxxxxx-xxxx-4xxx-8xxx-xxxxxxxxxxxx"
                      />
                    </div>
                    <div className="space-y-1">
                      <Label htmlFor="comp-base-amount">Base amount</Label>
                      <Input
                        id="comp-base-amount"
                        value={baseAmount}
                        onChange={(event) => setBaseAmount(event.target.value)}
                        placeholder="0.00"
                      />
                    </div>
                    <div className="grid gap-4 md:grid-cols-2">
                      <div className="space-y-1">
                        <Label htmlFor="comp-effective-from">Effective from</Label>
                        <Input
                          id="comp-effective-from"
                          type="date"
                          value={effectiveFrom}
                          onChange={(event) => setEffectiveFrom(event.target.value)}
                        />
                      </div>
                      <div className="space-y-1">
                        <Label htmlFor="comp-effective-to">Effective to (optional)</Label>
                        <Input
                          id="comp-effective-to"
                          type="date"
                          value={effectiveTo}
                          onChange={(event) => setEffectiveTo(event.target.value)}
                        />
                      </div>
                    </div>
                    <div className="space-y-1">
                      <Label htmlFor="comp-overrides-json">Overrides JSON (optional)</Label>
                      <textarea
                        id="comp-overrides-json"
                        className="min-h-32 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                        value={overridesJson}
                        onChange={(event) => setOverridesJson(event.target.value)}
                        placeholder='{"housing_allowance": "1500.00"}'
                      />
                    </div>
                  </div>
                  <SheetFooter>
                    <Button
                      type="button"
                      disabled={createM.isPending}
                      onClick={() => void onCreate()}
                    >
                      {createM.isPending ? "Saving..." : "Add compensation record"}
                    </Button>
                  </SheetFooter>
                </SheetContent>
              </Sheet>
            ) : null
          }
        />
      }
      main={
        employeeId ? (
          <DataTable
            isLoading={compensationQ.isLoading}
            error={compensationQ.error}
            onRetry={() => void compensationQ.refetch()}
            isEmpty={!compensationQ.isLoading && !compensationQ.error && compensation.length === 0}
            emptyState={
              <EmptyState
                title="No compensation records"
                description="Add an effective-dated compensation record for this employee."
                align="center"
              />
            }
            skeleton={{ rows: 6, cols: 6 }}
          >
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Effective from</TableHead>
                  <TableHead>Effective to</TableHead>
                  <TableHead>Currency</TableHead>
                  <TableHead>Base amount</TableHead>
                  <TableHead>Structure</TableHead>
                  <TableHead>Created</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {compensation.map((record) => (
                  <TableRow key={record.id}>
                    <TableCell className="font-medium">{record.effective_from}</TableCell>
                    <TableCell>{formatDate(record.effective_to)}</TableCell>
                    <TableCell>{record.currency_code}</TableCell>
                    <TableCell>{formatPayrollMoney(record.base_amount, record.currency_code)}</TableCell>
                    <TableCell className="text-text-2">{record.salary_structure_id}</TableCell>
                    <TableCell className="text-text-2">{formatDateTime(record.created_at)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </DataTable>
        ) : (
          <EmployeePickerCard
            employees={employees}
            isLoading={employeesQ.isLoading}
            error={employeesQ.error}
            onRetry={() => void employeesQ.refetch()}
            search={employeeSearch}
            onSearch={setEmployeeSearch}
            onSelect={setEmployee}
          />
        )
      }
      right={
        <RightPanelStack>
          <DSCard surface="panel" className="space-y-4 p-[var(--ds-space-16)]">
            <div>
              <div className="text-sm font-semibold tracking-tight text-text-1">Selected employee</div>
              {employee ? (
                <div className="mt-1 text-sm text-text-2">
                  {employee.person.first_name} {employee.person.last_name}
                </div>
              ) : (
                <div className="mt-1 text-sm text-text-2">Choose an employee to view compensation history.</div>
              )}
            </div>
            {employee ? (
              <>
                <div className="space-y-2 text-sm text-text-2">
                  <div>Employee code: {employee.employee.employee_code}</div>
                  <div>Email: {employee.person.email ?? "—"}</div>
                  <div>Branch: {employee.current_employment?.branch_id ?? "—"}</div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <StatusChip status={employee.employee.status} />
                  <Button asChild size="sm" type="button" variant="outline">
                    <Link href={`/hr/employees/${employee.employee.id}`}>Open employee</Link>
                  </Button>
                </div>
              </>
            ) : null}
          </DSCard>

          <DSCard surface="panel" className="space-y-4 p-[var(--ds-space-16)]">
            <div>
              <div className="text-sm font-semibold tracking-tight text-text-1">Prefilled structure</div>
              {structureIdPrefill ? (
                <div className="mt-1 text-sm text-text-2">{structureIdPrefill}</div>
              ) : (
                <div className="mt-1 text-sm text-text-2">No structure prefilled.</div>
              )}
            </div>
            {structureQ.isError ? (
              <ErrorState
                title="Could not load structure"
                error={structureQ.error}
                onRetry={() => void structureQ.refetch()}
                variant="inline"
                className="max-w-none"
              />
            ) : structureQ.data ? (
              <div className="space-y-2 text-sm text-text-2">
                <div>Name: {structureQ.data.structure.name}</div>
                <div>Code: {structureQ.data.structure.code}</div>
                <div>Lines: {structureQ.data.lines.length}</div>
                <Button asChild size="sm" type="button" variant="outline">
                  <Link href={`/payroll/structures/${structureQ.data.structure.id}`}>Open structure</Link>
                </Button>
              </div>
            ) : (
              <div className="text-sm text-text-3">
                Salary structures do not have a browse endpoint in v1. Use a structure UUID or open this page from a structure detail flow.
              </div>
            )}
          </DSCard>
        </RightPanelStack>
      }
    />
  );
}
