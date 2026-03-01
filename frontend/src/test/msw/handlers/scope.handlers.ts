import { http, HttpResponse } from "msw";

import { ok } from "@/test/msw/builders/response";

/**
 * Scope-related handlers.
 *
 * These endpoints are often hit by "context picker" UI in the shell.
 */
export const scopeHandlers = [
  http.get("*/api/v1/branches/*/cameras", () => HttpResponse.json(ok([]))),
];

