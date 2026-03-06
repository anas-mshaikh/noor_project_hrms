/**
 * lib/dateRange.ts
 *
 * Local-time safe date helpers for UI + query params.
 *
 * IMPORTANT:
 * - Do NOT use `toISOString().slice(0,10)` for date inputs; it is UTC-based and
 *   can shift the calendar day for users in non-UTC timezones.
 */

export function ymdFromDateLocal(d: Date): string {
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

export function parseYmdLocal(value: string): Date | null {
  // Expect YYYY-MM-DD.
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value));
  if (!m) return null;
  const yyyy = Number(m[1]);
  const mm = Number(m[2]);
  const dd = Number(m[3]);
  if (!Number.isFinite(yyyy) || !Number.isFinite(mm) || !Number.isFinite(dd))
    return null;
  if (mm < 1 || mm > 12) return null;
  if (dd < 1 || dd > 31) return null;

  const d = new Date(yyyy, mm - 1, dd);
  // Validate that Date didn't overflow (e.g. 2026-02-31).
  if (d.getFullYear() !== yyyy) return null;
  if (d.getMonth() !== mm - 1) return null;
  if (d.getDate() !== dd) return null;
  return d;
}

export function startOfMonthLocal(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), 1);
}

export function endOfMonthLocal(d: Date): Date {
  // Day 0 of next month = last day of current month.
  return new Date(d.getFullYear(), d.getMonth() + 1, 0);
}

export function addMonthsLocal(d: Date, deltaMonths: number): Date {
  // Always return a stable first-of-month date to avoid day overflow.
  return new Date(d.getFullYear(), d.getMonth() + deltaMonths, 1);
}

export function monthRangeLocal(month: Date): {
  fromDate: Date;
  toDate: Date;
  from: string;
  to: string;
} {
  const fromDate = startOfMonthLocal(month);
  const toDate = endOfMonthLocal(month);
  return {
    fromDate,
    toDate,
    from: ymdFromDateLocal(fromDate),
    to: ymdFromDateLocal(toDate),
  };
}

export function eachDayInclusiveLocal(fromDate: Date, toDate: Date): Date[] {
  const out: Date[] = [];
  const cur = new Date(
    fromDate.getFullYear(),
    fromDate.getMonth(),
    fromDate.getDate(),
  );
  const end = new Date(
    toDate.getFullYear(),
    toDate.getMonth(),
    toDate.getDate(),
  );

  while (cur <= end) {
    out.push(new Date(cur.getFullYear(), cur.getMonth(), cur.getDate()));
    cur.setDate(cur.getDate() + 1);
  }
  return out;
}
