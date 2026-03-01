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

test("login page loads", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByRole("heading")).toBeVisible();
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

