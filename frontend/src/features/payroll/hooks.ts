"use client";

import { useMutation, useQuery } from "@tanstack/react-query";

import {
  addSalaryStructureLine,
  createPayrollCalendar,
  createPayrollComponent,
  createPayrollPeriod,
  createSalaryStructure,
  generatePayrun,
  getMyPayslip,
  getPayrun,
  getSalaryStructure,
  listEmployeeCompensation,
  listMyPayslips,
  listPayrollCalendars,
  listPayrollComponents,
  listPayrollPeriods,
  publishPayrun,
  submitPayrunApproval,
  upsertEmployeeCompensation,
} from "@/features/payroll/api/payroll";
import { payrollKeys } from "@/features/payroll/queryKeys";
import type {
  EmployeeCompensationUpsertIn,
  PayrollCalendarCreateIn,
  PayrollComponentCreateIn,
  PayrollPeriodCreateIn,
  PayrunGenerateIn,
  SalaryStructureCreateIn,
  SalaryStructureLineCreateIn,
  UUID,
} from "@/lib/types";

export function usePayrollCalendars(enabled = true) {
  return useQuery({
    queryKey: payrollKeys.calendars(),
    enabled,
    queryFn: () => listPayrollCalendars(),
  });
}

export function usePayrollPeriods(calendarId: UUID | null, year: number, enabled = true) {
  return useQuery({
    queryKey: payrollKeys.periods(calendarId, year),
    enabled: Boolean(calendarId && enabled),
    queryFn: () => listPayrollPeriods(calendarId as UUID, year),
  });
}

export function usePayrollComponents(type: string | null, enabled = true) {
  return useQuery({
    queryKey: payrollKeys.components(type),
    enabled,
    queryFn: () => listPayrollComponents({ type }),
  });
}

export function useSalaryStructure(structureId: UUID | null, enabled = true) {
  return useQuery({
    queryKey: payrollKeys.structure(structureId),
    enabled: Boolean(structureId && enabled),
    queryFn: () => getSalaryStructure(structureId as UUID),
  });
}

export function useEmployeeCompensation(employeeId: UUID | null, enabled = true) {
  return useQuery({
    queryKey: payrollKeys.employeeCompensation(employeeId),
    enabled: Boolean(employeeId && enabled),
    queryFn: () => listEmployeeCompensation(employeeId as UUID),
  });
}

export function usePayrun(payrunId: UUID | null, includeLines: boolean, enabled = true) {
  return useQuery({
    queryKey: payrollKeys.payrun(payrunId, includeLines),
    enabled: Boolean(payrunId && enabled),
    queryFn: () => getPayrun(payrunId as UUID, includeLines),
  });
}

export function useMyPayslips(year: number, enabled = true) {
  return useQuery({
    queryKey: payrollKeys.payslipsMe(year),
    enabled,
    queryFn: () => listMyPayslips(year),
  });
}

export function usePayrollCalendarCreate() {
  return useMutation({ mutationFn: (payload: PayrollCalendarCreateIn) => createPayrollCalendar(payload) });
}

export function usePayrollPeriodCreate(calendarId: UUID) {
  return useMutation({ mutationFn: (payload: PayrollPeriodCreateIn) => createPayrollPeriod(calendarId, payload) });
}

export function usePayrollComponentCreate() {
  return useMutation({ mutationFn: (payload: PayrollComponentCreateIn) => createPayrollComponent(payload) });
}

export function useSalaryStructureCreate() {
  return useMutation({ mutationFn: (payload: SalaryStructureCreateIn) => createSalaryStructure(payload) });
}

export function useSalaryStructureLineCreate(structureId: UUID) {
  return useMutation({ mutationFn: (payload: SalaryStructureLineCreateIn) => addSalaryStructureLine(structureId, payload) });
}

export function useEmployeeCompensationUpsert(employeeId: UUID) {
  return useMutation({ mutationFn: (payload: EmployeeCompensationUpsertIn) => upsertEmployeeCompensation(employeeId, payload) });
}

export function usePayrunGenerate() {
  return useMutation({ mutationFn: (payload: PayrunGenerateIn) => generatePayrun(payload) });
}

export function usePayrunSubmitApproval(payrunId: UUID) {
  return useMutation({ mutationFn: () => submitPayrunApproval(payrunId) });
}

export function usePayrunPublish(payrunId: UUID) {
  return useMutation({ mutationFn: () => publishPayrun(payrunId) });
}

export function useMyPayslip(payslipId: UUID | null, enabled = true) {
  return useQuery({
    queryKey: ["payroll", "payslip", payslipId],
    enabled: Boolean(payslipId && enabled),
    queryFn: () => getMyPayslip(payslipId as UUID),
  });
}
