"use client";

import * as React from "react";
import { toast } from "sonner";
import { useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/lib/auth";
import { toastApiError } from "@/lib/toastApiError";
import type { PayrollCalendarCreateIn, PayrollCalendarOut, PayrollPeriodCreateIn } from "@/lib/types";
import {
  usePayrollCalendarCreate,
  usePayrollCalendars,
  usePayrollPeriodCreate,
  usePayrollPeriods,
} from "@/features/payroll/hooks";
import { payrollKeys } from "@/features/payroll/queryKeys";
import { currentPayrollYear, isValidPeriodKey } from "@/features/payroll/utils/periods";

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
import { Sheet, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

function formatDate(value: string): string {
  return value;
}

export default function PayrollCalendarsPage() {
  const user = useAuth((s) => s.user);
  const permissions = useAuth((s) => s.permissions);
  const granted = React.useMemo(() => new Set(permissions ?? []), [permissions]);
  const canRead = granted.has("payroll:calendar:read");
  const canWrite = granted.has("payroll:calendar:write");
  const qc = useQueryClient();

  const calendarsQ = usePayrollCalendars(Boolean(user && canRead));
  const [selectedId, setSelectedId] = React.useState<string | null>(null);
  const calendars = React.useMemo(() => calendarsQ.data ?? [], [calendarsQ.data]);
  const selected = React.useMemo(
    () => (selectedId ? calendars.find((calendar) => calendar.id === selectedId) ?? null : calendars[0] ?? null),
    [calendars, selectedId],
  );
  React.useEffect(() => {
    if (!selectedId && calendars[0]) setSelectedId(calendars[0].id);
  }, [calendars, selectedId]);

  const [year, setYear] = React.useState(currentPayrollYear());
  const periodsQ = usePayrollPeriods(selected?.id ?? null, year, Boolean(selected && canRead));
  const periods = periodsQ.data ?? [];

  const [calendarOpen, setCalendarOpen] = React.useState(false);
  const [calendarCode, setCalendarCode] = React.useState("");
  const [calendarName, setCalendarName] = React.useState("");
  const [currencyCode, setCurrencyCode] = React.useState("SAR");
  const [timezone, setTimezone] = React.useState("Asia/Riyadh");
  const [isActive, setIsActive] = React.useState(true);
  const createCalendarM = usePayrollCalendarCreate();

  const [periodOpen, setPeriodOpen] = React.useState(false);
  const [periodKey, setPeriodKey] = React.useState("");
  const [startDate, setStartDate] = React.useState("");
  const [endDate, setEndDate] = React.useState("");
  const createPeriodM = usePayrollPeriodCreate(selected?.id ?? ("" as PayrollCalendarOut["id"]));

  if (!user) {
    return <ErrorState title="Sign in required" error={new Error("Please sign in to manage payroll calendars.")} />;
  }

  if (!canRead) {
    return <ErrorState title="Access denied" error={new Error("Your account does not have access to payroll calendars.")} />;
  }

  async function onCreateCalendar() {
    const payload: PayrollCalendarCreateIn = {
      code: calendarCode.trim(),
      name: calendarName.trim(),
      currency_code: currencyCode.trim(),
      timezone: timezone.trim(),
      is_active: isActive,
    };
    if (!payload.code || !payload.name || !payload.currency_code || !payload.timezone) {
      toast.error("Complete all calendar fields.");
      return;
    }
    try {
      const created = await createCalendarM.mutateAsync(payload);
      await qc.invalidateQueries({ queryKey: payrollKeys.calendars() });
      setSelectedId(created.id);
      setCalendarOpen(false);
      setCalendarCode("");
      setCalendarName("");
      setCurrencyCode("SAR");
      setTimezone("Asia/Riyadh");
      setIsActive(true);
      toast.success("Payroll calendar created");
    } catch (err) {
      toastApiError(err);
    }
  }

  async function onCreatePeriod() {
    if (!selected) return;
    const payload: PayrollPeriodCreateIn = {
      period_key: periodKey.trim(),
      start_date: startDate,
      end_date: endDate,
    };
    if (!isValidPeriodKey(payload.period_key)) {
      toast.error("Use YYYY-MM for the period key.");
      return;
    }
    if (!payload.start_date || !payload.end_date) {
      toast.error("Select a start and end date.");
      return;
    }
    try {
      await createPeriodM.mutateAsync(payload);
      await qc.invalidateQueries({ queryKey: payrollKeys.periods(selected.id, year) });
      setPeriodOpen(false);
      setPeriodKey("");
      setStartDate("");
      setEndDate("");
      toast.success("Payroll period created");
    } catch (err) {
      toastApiError(err);
    }
  }

  return (
    <ListRightPanelTemplate
      header={
        <PageHeader
          title="Payroll calendars"
          subtitle="Monthly calendars and explicit payroll periods."
          actions={
            canWrite ? (
              <Sheet open={calendarOpen} onOpenChange={setCalendarOpen}>
                <SheetTrigger asChild>
                  <Button type="button">Create calendar</Button>
                </SheetTrigger>
                <SheetContent className="border-border-subtle bg-surface-2 backdrop-blur-xl">
                  <SheetHeader>
                    <SheetTitle>Create payroll calendar</SheetTitle>
                    <SheetDescription>Calendars are tenant-scoped and currently monthly only.</SheetDescription>
                  </SheetHeader>
                  <div className="space-y-4 px-4">
                    <div className="space-y-1"><Label htmlFor="calendar-code">Code</Label><Input id="calendar-code" value={calendarCode} onChange={(e) => setCalendarCode(e.target.value)} /></div>
                    <div className="space-y-1"><Label htmlFor="calendar-name">Name</Label><Input id="calendar-name" value={calendarName} onChange={(e) => setCalendarName(e.target.value)} /></div>
                    <div className="space-y-1"><Label htmlFor="calendar-currency">Currency</Label><Input id="calendar-currency" value={currencyCode} onChange={(e) => setCurrencyCode(e.target.value)} /></div>
                    <div className="space-y-1"><Label htmlFor="calendar-timezone">Timezone</Label><Input id="calendar-timezone" value={timezone} onChange={(e) => setTimezone(e.target.value)} /></div>
                    <label className="flex items-center gap-2 text-sm text-text-2"><input type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} /> Active</label>
                  </div>
                  <SheetFooter>
                    <Button type="button" disabled={createCalendarM.isPending} onClick={() => void onCreateCalendar()}>
                      {createCalendarM.isPending ? "Creating..." : "Create calendar"}
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
          isLoading={calendarsQ.isLoading}
          error={calendarsQ.error}
          onRetry={() => void calendarsQ.refetch()}
          isEmpty={!calendarsQ.isLoading && !calendarsQ.error && calendars.length === 0}
          emptyState={<EmptyState title="No payroll calendars" description="Create a payroll calendar to start defining periods." align="center" />}
          skeleton={{ rows: 6, cols: 4 }}
        >
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Code</TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Currency</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {calendars.map((calendar) => (
                <TableRow key={calendar.id} className="cursor-pointer" onClick={() => setSelectedId(calendar.id)}>
                  <TableCell className="font-medium">{calendar.code}</TableCell>
                  <TableCell>{calendar.name}</TableCell>
                  <TableCell>{calendar.currency_code}</TableCell>
                  <TableCell><StatusChip status={calendar.is_active ? "ACTIVE" : "INACTIVE"} /></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </DataTable>
      }
      right={
        <RightPanelStack>
          <DSCard surface="panel" className="space-y-4 p-[var(--ds-space-16)]">
            <div>
              <div className="text-sm font-semibold tracking-tight text-text-1">Selected calendar</div>
              <div className="mt-1 text-sm text-text-2">{selected ? `${selected.name} (${selected.code})` : "Choose a calendar"}</div>
            </div>
            {selected ? (
              <>
                <div className="flex items-center gap-2">
                  <Label htmlFor="period-year" className="text-xs text-text-2">Year</Label>
                  <Input id="period-year" type="number" value={year} onChange={(e) => setYear(Number(e.target.value) || currentPayrollYear())} />
                </div>
                {canWrite ? (
                  <Sheet open={periodOpen} onOpenChange={setPeriodOpen}>
                    <SheetTrigger asChild>
                      <Button type="button" variant="secondary">Create period</Button>
                    </SheetTrigger>
                    <SheetContent className="border-border-subtle bg-surface-2 backdrop-blur-xl">
                      <SheetHeader>
                        <SheetTitle>Create payroll period</SheetTitle>
                        <SheetDescription>Periods are explicit inclusive date ranges for a calendar.</SheetDescription>
                      </SheetHeader>
                      <div className="space-y-4 px-4">
                        <div className="space-y-1"><Label htmlFor="period-key">Period key</Label><Input id="period-key" value={periodKey} onChange={(e) => setPeriodKey(e.target.value)} placeholder="2026-03" /></div>
                        <div className="space-y-1"><Label htmlFor="period-start">Start date</Label><Input id="period-start" type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} /></div>
                        <div className="space-y-1"><Label htmlFor="period-end">End date</Label><Input id="period-end" type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} /></div>
                      </div>
                      <SheetFooter>
                        <Button type="button" disabled={createPeriodM.isPending} onClick={() => void onCreatePeriod()}>
                          {createPeriodM.isPending ? "Creating..." : "Create period"}
                        </Button>
                      </SheetFooter>
                    </SheetContent>
                  </Sheet>
                ) : null}
                <DataTable
                  isLoading={periodsQ.isLoading}
                  error={periodsQ.error}
                  onRetry={() => void periodsQ.refetch()}
                  isEmpty={!periodsQ.isLoading && !periodsQ.error && periods.length === 0}
                  emptyState={<EmptyState title="No periods for this year" description="Create a payroll period for the selected year." align="center" />}
                  skeleton={{ rows: 4, cols: 3 }}
                >
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Key</TableHead>
                        <TableHead>Range</TableHead>
                        <TableHead>Status</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {periods.map((period) => (
                        <TableRow key={period.id}>
                          <TableCell className="font-medium">{period.period_key}</TableCell>
                          <TableCell>{formatDate(period.start_date)} to {formatDate(period.end_date)}</TableCell>
                          <TableCell><StatusChip status={period.status} /></TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </DataTable>
              </>
            ) : (
              <EmptyState title="Select a calendar" description="Periods are shown for the selected calendar." align="center" />
            )}
          </DSCard>
        </RightPanelStack>
      }
    />
  );
}
