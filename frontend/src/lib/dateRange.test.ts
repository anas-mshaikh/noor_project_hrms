import { describe, expect, it } from "vitest";

import {
  addMonthsLocal,
  eachDayInclusiveLocal,
  endOfMonthLocal,
  monthRangeLocal,
  parseYmdLocal,
  startOfMonthLocal,
  ymdFromDateLocal,
} from "./dateRange";

describe("lib/dateRange", () => {
  it("formats YYYY-MM-DD in local time", () => {
    const d = new Date(2026, 0, 2); // Jan 2, 2026 (local)
    expect(ymdFromDateLocal(d)).toBe("2026-01-02");
  });

  it("parses valid YYYY-MM-DD into a local Date", () => {
    const d = parseYmdLocal("2026-03-04");
    expect(d).not.toBeNull();
    expect(d?.getFullYear()).toBe(2026);
    expect(d?.getMonth()).toBe(2); // 0-indexed
    expect(d?.getDate()).toBe(4);
  });

  it("rejects invalid dates", () => {
    expect(parseYmdLocal("nope")).toBeNull();
    expect(parseYmdLocal("2026-13-01")).toBeNull();
    expect(parseYmdLocal("2026-02-31")).toBeNull();
  });

  it("computes start/end of month deterministically", () => {
    const base = new Date(2026, 1, 10); // Feb 10 2026
    expect(ymdFromDateLocal(startOfMonthLocal(base))).toBe("2026-02-01");
    expect(ymdFromDateLocal(endOfMonthLocal(base))).toBe("2026-02-28");
  });

  it("adds months without day overflow", () => {
    const jan = new Date(2026, 0, 31); // Jan 31
    const next = addMonthsLocal(jan, 1);
    // We intentionally pin to the 1st to avoid Feb overflow.
    expect(ymdFromDateLocal(next)).toBe("2026-02-01");
  });

  it("computes a month range", () => {
    const base = new Date(2026, 2, 15); // Mar 15
    const r = monthRangeLocal(base);
    expect(r.from).toBe("2026-03-01");
    expect(r.to).toBe("2026-03-31");
  });

  it("iterates inclusive day ranges", () => {
    const days = eachDayInclusiveLocal(
      new Date(2026, 0, 1),
      new Date(2026, 0, 3),
    );
    expect(days.map(ymdFromDateLocal)).toEqual([
      "2026-01-01",
      "2026-01-02",
      "2026-01-03",
    ]);
  });
});
