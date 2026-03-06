import { http, HttpResponse } from "msw";

import { ok } from "@/test/msw/builders/response";

/**
 * Leave handlers (safe defaults).
 *
 * Individual tests should override with `server.use(...)` as needed.
 */
export const leaveHandlers = [
  http.get("*/api/v1/leave/me/balances", () =>
    HttpResponse.json(ok({ items: [] })),
  ),

  http.get("*/api/v1/leave/me/requests", () =>
    HttpResponse.json(ok({ items: [], next_cursor: null })),
  ),

  http.get("*/api/v1/leave/team/calendar", () =>
    HttpResponse.json(ok({ items: [] })),
  ),
];
