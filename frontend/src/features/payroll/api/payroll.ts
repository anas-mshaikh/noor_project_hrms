import { apiDownload, apiJson } from "@/lib/api";
import type {
  EmployeeCompensationOut,
  EmployeeCompensationUpsertIn,
  PayrollCalendarCreateIn,
  PayrollCalendarOut,
  PayrollComponentCreateIn,
  PayrollComponentOut,
  PayrollPeriodCreateIn,
  PayrollPeriodOut,
  PayrunDetailOut,
  PayrunGenerateIn,
  PayrunOut,
  PayrunPublishOut,
  PayrunSubmitApprovalOut,
  PayslipListOut,
  PayslipOut,
  SalaryStructureCreateIn,
  SalaryStructureDetailOut,
  SalaryStructureLineCreateIn,
  SalaryStructureLineOut,
  SalaryStructureOut,
  UUID,
} from "@/lib/types";

export async function createPayrollCalendar(
  payload: PayrollCalendarCreateIn,
  init?: RequestInit,
): Promise<PayrollCalendarOut> {
  return apiJson<PayrollCalendarOut>("/api/v1/payroll/calendars", {
    method: "POST",
    body: JSON.stringify(payload),
    ...init,
  });
}

export async function listPayrollCalendars(init?: RequestInit): Promise<PayrollCalendarOut[]> {
  return apiJson<PayrollCalendarOut[]>("/api/v1/payroll/calendars", init);
}

export async function createPayrollPeriod(
  calendarId: UUID,
  payload: PayrollPeriodCreateIn,
  init?: RequestInit,
): Promise<PayrollPeriodOut> {
  return apiJson<PayrollPeriodOut>(`/api/v1/payroll/calendars/${calendarId}/periods`, {
    method: "POST",
    body: JSON.stringify(payload),
    ...init,
  });
}

export async function listPayrollPeriods(
  calendarId: UUID,
  year: number,
  init?: RequestInit,
): Promise<PayrollPeriodOut[]> {
  const qs = new URLSearchParams({ year: String(year) });
  return apiJson<PayrollPeriodOut[]>(
    `/api/v1/payroll/calendars/${calendarId}/periods?${qs.toString()}`,
    init,
  );
}

export async function createPayrollComponent(
  payload: PayrollComponentCreateIn,
  init?: RequestInit,
): Promise<PayrollComponentOut> {
  return apiJson<PayrollComponentOut>("/api/v1/payroll/components", {
    method: "POST",
    body: JSON.stringify(payload),
    ...init,
  });
}

export async function listPayrollComponents(
  args?: { type?: string | null },
  init?: RequestInit,
): Promise<PayrollComponentOut[]> {
  const qs = new URLSearchParams();
  if (args?.type) qs.set("type", args.type);
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return apiJson<PayrollComponentOut[]>(`/api/v1/payroll/components${suffix}`, init);
}

export async function createSalaryStructure(
  payload: SalaryStructureCreateIn,
  init?: RequestInit,
): Promise<SalaryStructureOut> {
  return apiJson<SalaryStructureOut>("/api/v1/payroll/salary-structures", {
    method: "POST",
    body: JSON.stringify(payload),
    ...init,
  });
}

export async function getSalaryStructure(
  structureId: UUID,
  init?: RequestInit,
): Promise<SalaryStructureDetailOut> {
  return apiJson<SalaryStructureDetailOut>(`/api/v1/payroll/salary-structures/${structureId}`, init);
}

export async function addSalaryStructureLine(
  structureId: UUID,
  payload: SalaryStructureLineCreateIn,
  init?: RequestInit,
): Promise<SalaryStructureLineOut> {
  return apiJson<SalaryStructureLineOut>(
    `/api/v1/payroll/salary-structures/${structureId}/lines`,
    {
      method: "POST",
      body: JSON.stringify(payload),
      ...init,
    },
  );
}

export async function upsertEmployeeCompensation(
  employeeId: UUID,
  payload: EmployeeCompensationUpsertIn,
  init?: RequestInit,
): Promise<EmployeeCompensationOut> {
  return apiJson<EmployeeCompensationOut>(`/api/v1/payroll/employees/${employeeId}/compensation`, {
    method: "POST",
    body: JSON.stringify(payload),
    ...init,
  });
}

export async function listEmployeeCompensation(
  employeeId: UUID,
  init?: RequestInit,
): Promise<EmployeeCompensationOut[]> {
  return apiJson<EmployeeCompensationOut[]>(`/api/v1/payroll/employees/${employeeId}/compensation`, init);
}

export async function generatePayrun(
  payload: PayrunGenerateIn,
  init?: RequestInit,
): Promise<PayrunOut> {
  return apiJson<PayrunOut>("/api/v1/payroll/payruns/generate", {
    method: "POST",
    body: JSON.stringify(payload),
    ...init,
  });
}

export async function getPayrun(
  payrunId: UUID,
  includeLines = false,
  init?: RequestInit,
): Promise<PayrunDetailOut> {
  const qs = new URLSearchParams({ include_lines: includeLines ? "1" : "0" });
  return apiJson<PayrunDetailOut>(`/api/v1/payroll/payruns/${payrunId}?${qs.toString()}`, init);
}

export async function submitPayrunApproval(
  payrunId: UUID,
  init?: RequestInit,
): Promise<PayrunSubmitApprovalOut> {
  return apiJson<PayrunSubmitApprovalOut>(`/api/v1/payroll/payruns/${payrunId}/submit-approval`, {
    method: "POST",
    ...init,
  });
}

export async function publishPayrun(
  payrunId: UUID,
  init?: RequestInit,
): Promise<PayrunPublishOut> {
  return apiJson<PayrunPublishOut>(`/api/v1/payroll/payruns/${payrunId}/publish`, {
    method: "POST",
    ...init,
  });
}

export async function exportPayrun(
  payrunId: UUID,
  init?: RequestInit & { filename?: string },
) {
  return apiDownload(`/api/v1/payroll/payruns/${payrunId}/export?format=csv`, init);
}

export async function listMyPayslips(
  year: number,
  init?: RequestInit,
): Promise<PayslipListOut> {
  const qs = new URLSearchParams({ year: String(year) });
  return apiJson<PayslipListOut>(`/api/v1/ess/me/payslips?${qs.toString()}`, init);
}

export async function getMyPayslip(
  payslipId: UUID,
  init?: RequestInit,
): Promise<PayslipOut> {
  return apiJson<PayslipOut>(`/api/v1/ess/me/payslips/${payslipId}`, init);
}

export async function downloadMyPayslip(
  payslipId: UUID,
  init?: RequestInit & { filename?: string },
) {
  return apiDownload(`/api/v1/ess/me/payslips/${payslipId}/download`, init);
}
