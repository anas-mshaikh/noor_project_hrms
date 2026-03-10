export function currentPayrollYear(now = new Date()): number {
  return now.getFullYear();
}

export function isValidPeriodKey(value: string): boolean {
  return /^[0-9]{4}-[0-9]{2}$/.test(String(value));
}

export function yearFromPeriodKey(value: string): number | null {
  if (!isValidPeriodKey(value)) return null;
  return Number(value.slice(0, 4));
}
