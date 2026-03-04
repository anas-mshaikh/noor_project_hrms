import { http, HttpResponse } from "msw";

import { ok } from "@/test/msw/builders/response";

const SAMPLE_PROFILE = {
  employee: {
    id: "e-1",
    tenant_id: "t-1",
    company_id: "c-1",
    person_id: "p-1",
    employee_code: "E0001",
    status: "ACTIVE",
    join_date: null,
    termination_date: null,
    created_at: new Date(0).toISOString(),
    updated_at: new Date(0).toISOString(),
  },
  person: {
    id: "p-1",
    tenant_id: "t-1",
    first_name: "Sample",
    last_name: "Employee",
    dob: null,
    nationality: null,
    email: "sample@example.com",
    phone: null,
    address: {},
    created_at: new Date(0).toISOString(),
    updated_at: new Date(0).toISOString(),
  },
  current_employment: null,
  manager: null,
  linked_user: null,
};

/**
 * ESS handlers (safe defaults).
 *
 * Individual tests should override with `server.use(...)` as needed.
 */
export const essHandlers = [
  http.get("*/api/v1/ess/me/profile", () => HttpResponse.json(ok(SAMPLE_PROFILE))),
  http.patch("*/api/v1/ess/me/profile", () => HttpResponse.json(ok(SAMPLE_PROFILE))),
];

