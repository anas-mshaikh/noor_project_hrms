import { http, HttpResponse } from "msw";

import { ok } from "@/test/msw/builders/response";

/**
 * Attendance handlers (safe defaults).
 *
 * Individual tests should override with `server.use(...)` as needed.
 */

export const attendanceHandlers = [
  http.get("*/api/v1/attendance/me/punch-state", () => {
    const today = "2026-01-01";
    return HttpResponse.json(
      ok({
        today_business_date: today,
        is_punched_in: false,
        open_session_started_at: null,
        base_minutes_today: 0,
        effective_minutes_today: 0,
        effective_status_today: "ABSENT",
      }),
    );
  }),

  http.post("*/api/v1/attendance/me/punch-in", () => {
    const today = "2026-01-01";
    return HttpResponse.json(
      ok({
        today_business_date: today,
        is_punched_in: true,
        open_session_started_at: new Date(0).toISOString(),
        base_minutes_today: 0,
        effective_minutes_today: 0,
        effective_status_today: "PRESENT",
      }),
    );
  }),

  http.post("*/api/v1/attendance/me/punch-out", () => {
    const today = "2026-01-01";
    return HttpResponse.json(
      ok({
        today_business_date: today,
        is_punched_in: false,
        open_session_started_at: null,
        base_minutes_today: 0,
        effective_minutes_today: 0,
        effective_status_today: "PRESENT",
      }),
    );
  }),

  http.get("*/api/v1/attendance/me/days", () =>
    HttpResponse.json(ok({ items: [] })),
  ),

  http.get("*/api/v1/attendance/me/corrections", () =>
    HttpResponse.json(ok({ items: [], next_cursor: null })),
  ),
];
