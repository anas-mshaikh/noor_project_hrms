import { http, HttpResponse } from "msw";

import { ok } from "@/test/msw/builders/response";

/**
 * Workflow handlers (safe defaults).
 *
 * Individual tests should override with `server.use(...)` as needed.
 */
export const workflowHandlers = [
  http.get("*/api/v1/workflow/inbox", () =>
    HttpResponse.json(ok({ items: [], next_cursor: null })),
  ),

  http.get("*/api/v1/workflow/outbox", () =>
    HttpResponse.json(ok({ items: [], next_cursor: null })),
  ),

  http.get("*/api/v1/workflow/definitions", () => HttpResponse.json(ok([]))),
];
