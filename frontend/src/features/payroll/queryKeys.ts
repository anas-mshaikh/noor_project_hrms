import type { UUID } from "@/lib/types";

export const payrollKeys = {
  calendars: () => ["payroll", "calendars"] as const,
  periods: (calendarId: UUID | null, year: number) =>
    ["payroll", "periods", calendarId, year] as const,
  components: (type: string | null) => ["payroll", "components", type] as const,
  structure: (structureId: UUID | null) => ["payroll", "structure", structureId] as const,
  employeeCompensation: (employeeId: UUID | null) =>
    ["payroll", "employee-compensation", employeeId] as const,
  payrun: (payrunId: UUID | null, includeLines: boolean) =>
    ["payroll", "payrun", payrunId, includeLines] as const,
  payslipsMe: (year: number) => ["payroll", "payslips", "me", year] as const,
};
