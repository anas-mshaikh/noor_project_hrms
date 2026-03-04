import { http, HttpResponse } from "msw";

import { ok } from "@/test/msw/builders/response";

/**
 * Tenancy domain handlers (safe defaults).
 *
 * Individual tests should override with `server.use(...)` as needed.
 */
export const tenancyHandlers = [
  http.get("*/api/v1/tenancy/companies", () => HttpResponse.json(ok([]))),
  http.get("*/api/v1/tenancy/branches", () => HttpResponse.json(ok([]))),
  http.get("*/api/v1/tenancy/org-units", () => HttpResponse.json(ok([]))),
];
