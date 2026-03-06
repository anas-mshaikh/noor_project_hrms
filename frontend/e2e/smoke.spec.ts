import { test, expect } from "@playwright/test";

/**
 * Minimal smoke tests for the Noor web app.
 *
 * These are intentionally light-weight and do not require a seeded DB:
 * - /login is reachable without backend calls
 * - /setup is reachable
 * - settings consoles render with mocked session + API responses
 */

async function mockSessionForSettings(page: import("@playwright/test").Page) {
  const session = {
    ok: true,
    data: {
      user: { id: "u-1", email: "admin@example.com", status: "ACTIVE" },
      roles: ["ADMIN"],
      permissions: [
        "tenancy:read",
        "tenancy:write",
        "iam:user:read",
        "iam:user:write",
        "iam:role:assign",
        "iam:permission:read",
      ],
      scope: {
        tenant_id: "t-1",
        company_id: "c-1",
        branch_id: "b-1",
        allowed_tenant_ids: ["t-1"],
        allowed_company_ids: ["c-1"],
        allowed_branch_ids: ["b-1"],
      },
    },
  };

  await page.route("**/api/v1/auth/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(session),
    });
  });

  // StorePicker (mounted in the shell sheet) may prefetch these in some builds.
  await page.route("**/api/v1/tenancy/companies", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        data: [
          {
            id: "c-1",
            tenant_id: "t-1",
            name: "Demo Company",
            legal_name: "Demo Company LLC",
            currency_code: "SAR",
            timezone: "Asia/Riyadh",
            status: "ACTIVE",
          },
        ],
      }),
    });
  });

  await page.route("**/api/v1/tenancy/branches**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ ok: true, data: [] }),
    });
  });

  await page.route("**/api/v1/branches/**/cameras", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ ok: true, data: [] }),
    });
  });

  await page.route("**/api/v1/iam/users**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        data: [
          {
            id: "u-1",
            email: "admin@example.com",
            phone: null,
            status: "ACTIVE",
            created_at: "2026-02-01T10:00:00Z",
          },
        ],
        meta: { limit: 20, offset: 0, total: 1 },
      }),
    });
  });
}

async function mockSessionForWorkflow(page: import("@playwright/test").Page) {
  const session = {
    ok: true,
    data: {
      user: { id: "u-wf-1", email: "approver@example.com", status: "ACTIVE" },
      roles: ["MANAGER"],
      permissions: ["workflow:request:read", "workflow:request:approve"],
      scope: {
        tenant_id: "t-1",
        company_id: "c-1",
        branch_id: "b-1",
        allowed_tenant_ids: ["t-1"],
        allowed_company_ids: ["c-1"],
        allowed_branch_ids: ["b-1"],
      },
    },
  };

  await page.route("**/api/v1/auth/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(session),
    });
  });

  // StorePicker (mounted in the shell sheet) may prefetch these in some builds.
  await page.route("**/api/v1/tenancy/companies", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        data: [
          {
            id: "c-1",
            tenant_id: "t-1",
            name: "Demo Company",
            legal_name: "Demo Company LLC",
            currency_code: "SAR",
            timezone: "Asia/Riyadh",
            status: "ACTIVE",
          },
        ],
      }),
    });
  });

  await page.route("**/api/v1/tenancy/branches**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ ok: true, data: [] }),
    });
  });

  // Workflow inbox/detail + approve flow (stateful).
  const requestId = "22222222-2222-4222-8222-222222222222";
  let approved = false;

  await page.route("**/api/v1/workflow/inbox**", async (route) => {
    const body = approved
      ? { ok: true, data: { items: [], next_cursor: null } }
      : {
          ok: true,
          data: {
            items: [
              {
                id: requestId,
                request_type_code: "profile.change",
                status: "PENDING",
                current_step: 0,
                subject: "Update email",
                payload: null,
                tenant_id: "t-1",
                company_id: "c-1",
                branch_id: "b-1",
                created_by_user_id: "u-wf-2",
                requester_employee_id: "e-1",
                subject_employee_id: null,
                entity_type: null,
                entity_id: null,
                created_at: "2026-03-01T10:00:00Z",
                updated_at: "2026-03-01T10:00:00Z",
              },
            ],
            next_cursor: null,
          },
        };

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(body),
    });
  });

  await page.route(`**/api/v1/workflow/requests/${requestId}`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        data: {
          request: {
            id: requestId,
            request_type_code: "profile.change",
            status: approved ? "APPROVED" : "PENDING",
            current_step: 0,
            subject: "Update email",
            payload: { field: "email", to: "new@example.com" },
            tenant_id: "t-1",
            company_id: "c-1",
            branch_id: "b-1",
            created_by_user_id: "u-wf-2",
            requester_employee_id: "e-1",
            subject_employee_id: null,
            entity_type: null,
            entity_id: null,
            created_at: "2026-03-01T10:00:00Z",
            updated_at: "2026-03-01T10:00:00Z",
          },
          steps: [],
          comments: [],
          attachments: [],
          events: [],
        },
      }),
    });
  });

  await page.route(`**/api/v1/workflow/requests/${requestId}/approve`, async (route) => {
    approved = true;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ ok: true, data: { id: requestId, status: "APPROVED", current_step: 0 } }),
    });
  });
}

test("login page loads", async ({ page }) => {
  await page.goto("/login");
  // Login page has multiple headings (e.g. "Sign in" + section titles). Assert the primary H1.
  await expect(
    page.getByRole("heading", { name: /sign in|iniciar sesi[oó]n/i })
  ).toBeVisible();
  await expect(page.getByRole("button", { name: /sign in|iniciar sesi[oó]n/i })).toBeVisible();
});

test("setup page loads (bootstrap UI)", async ({ page }) => {
  await page.goto("/setup");
  await expect(page.getByRole("heading", { name: /setup/i })).toBeVisible();
});

test("settings org + access pages load (mocked session)", async ({ page }) => {
  await mockSessionForSettings(page);

  await page.goto("/settings/org/companies");
  await expect(page.getByRole("heading", { name: /companies/i })).toBeVisible();

  await page.goto("/settings/access/users");
  await expect(page.getByRole("heading", { name: /users/i })).toBeVisible();
});

test.describe("workflow (mocked)", () => {
  test.skip(({ browserName }) => browserName !== "chromium", "chromium-only");

  test("inbox approve flow", async ({ page }) => {
    await mockSessionForWorkflow(page);

    await page.goto("/workflow/inbox");
    await expect(page.getByRole("heading", { name: /inbox/i })).toBeVisible();

    // Select request -> detail loads.
    await page.getByRole("button", { name: /profile\\.change/i }).click();
    await expect(page.getByText("Update email")).toBeVisible();

    // Approve -> request disappears from inbox pending list.
    await page.getByRole("button", { name: /^approve$/i }).click();
    await expect(page.getByText(/no requests/i)).toBeVisible();
  });
});
