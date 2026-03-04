import { http, HttpResponse } from "msw";

import { ok } from "@/test/msw/builders/response";

/**
 * MSS handlers (safe defaults).
 *
 * Individual tests should override with `server.use(...)` as needed.
 */
export const mssHandlers = [
  http.get("*/api/v1/mss/team", ({ request }) => {
    const url = new URL(request.url);
    const limit = Number(url.searchParams.get("limit") ?? 25);
    const offset = Number(url.searchParams.get("offset") ?? 0);
    return HttpResponse.json(
      ok({
        items: [],
        paging: { limit, offset, total: 0 },
      })
    );
  }),
];

