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

async function seedScope(
  page: import("@playwright/test").Page,
  scope: { tenantId: string; companyId: string; branchId: string },
) {
  await page.addInitScript((nextScope) => {
    window.localStorage.setItem(
      "attendance-admin-selection",
      JSON.stringify({ state: nextScope, version: 0 }),
    );
    document.cookie = `noor_scope_tenant_id=${nextScope.tenantId}; Path=/; SameSite=Lax`;
    document.cookie = `noor_scope_company_id=${nextScope.companyId}; Path=/; SameSite=Lax`;
    document.cookie = `noor_scope_branch_id=${nextScope.branchId}; Path=/; SameSite=Lax`;
  }, scope);
}

async function mockSessionForDms(page: import("@playwright/test").Page) {
  const scope = { tenantId: "t-1", companyId: "c-1", branchId: "b-1" };
  const employeeId = "30000000-0000-4000-8000-000000000001";
  const documentId = "10000000-0000-4000-8000-000000000001";
  const fileId = "00000000-0000-4000-8000-000000000001";
  const workflowRequestId = "40000000-0000-4000-8000-000000000001";

  await seedScope(page, scope);

  const session = {
    ok: true,
    data: {
      user: { id: "u-dms-1", email: "hr@example.com", status: "ACTIVE" },
      roles: ["HR"],
      permissions: [
        "hr:employee:read",
        "dms:document:read",
        "dms:document:write",
        "dms:document:verify",
        "dms:file:read",
        "dms:file:write",
        "workflow:request:read",
        "workflow:request:approve",
      ],
      scope: {
        tenant_id: scope.tenantId,
        company_id: scope.companyId,
        branch_id: scope.branchId,
        allowed_tenant_ids: [scope.tenantId],
        allowed_company_ids: [scope.companyId],
        allowed_branch_ids: [scope.branchId],
      },
    },
  };

  let uploaded = false;
  let verificationRequested = false;
  let approved = false;
  let downloadCount = 0;

  const currentDocument = () => ({
    id: documentId,
    tenant_id: scope.tenantId,
    document_type_id: "20000000-0000-4000-8000-000000000001",
    document_type_code: "PASSPORT",
    document_type_name: "Passport",
    owner_employee_id: employeeId,
    status: approved ? "VERIFIED" : "SUBMITTED",
    expires_at: "2026-12-31",
    current_version_id: "50000000-0000-4000-8000-000000000001",
    current_version: {
      id: "50000000-0000-4000-8000-000000000001",
      tenant_id: scope.tenantId,
      document_id: documentId,
      file_id: fileId,
      version: 1,
      notes: null,
      created_by_user_id: session.data.user.id,
      created_at: "2026-03-01T10:00:00Z",
    },
    verified_at: approved ? "2026-03-02T10:00:00Z" : null,
    verified_by_user_id: approved ? session.data.user.id : null,
    rejected_reason: null,
    created_by_user_id: session.data.user.id,
    verification_workflow_request_id: verificationRequested || approved ? workflowRequestId : null,
    created_at: "2026-03-01T10:00:00Z",
    updated_at: approved ? "2026-03-02T10:00:00Z" : "2026-03-01T10:00:00Z",
    meta: null,
  });

  await page.route("**/api/v1/auth/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(session),
    });
  });

  await page.route("**/api/v1/tenancy/companies", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        data: [
          {
            id: scope.companyId,
            tenant_id: scope.tenantId,
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

  await page.route(`**/api/v1/hr/employees/${employeeId}*`, async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname !== `/api/v1/hr/employees/${employeeId}`) {
      await route.fallback();
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        data: {
          employee: {
            id: employeeId,
            person_id: "person-1",
            employee_code: "E0001",
            status: "ACTIVE",
            join_date: "2026-01-01",
            termination_date: null,
          },
          person: {
            id: "person-1",
            first_name: "Alice",
            last_name: "One",
            email: "alice.one@example.com",
            phone: null,
          },
          current_employment: {
            employee_id: employeeId,
            branch_id: scope.branchId,
            org_unit_id: null,
            start_date: "2026-01-01",
            end_date: null,
            is_current: true,
          },
          linked_user: null,
        },
      }),
    });
  });

  await page.route("**/api/v1/dms/document-types", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        data: {
          items: [
            {
              id: "20000000-0000-4000-8000-000000000001",
              tenant_id: scope.tenantId,
              code: "PASSPORT",
              name: "Passport",
              requires_expiry: true,
              is_active: true,
              created_at: "2026-03-01T10:00:00Z",
              updated_at: "2026-03-01T10:00:00Z",
            },
          ],
        },
      }),
    });
  });

  await page.route(`**/api/v1/hr/employees/${employeeId}/documents**`, async (route) => {
    if (route.request().method() === "POST") {
      uploaded = true;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ok: true, data: currentDocument() }),
      });
      return;
    }

    const body = uploaded
      ? { ok: true, data: { items: [currentDocument()], next_cursor: null } }
      : { ok: true, data: { items: [], next_cursor: null } };

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(body),
    });
  });

  await page.route("**/api/v1/dms/files", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        data: {
          id: fileId,
          tenant_id: scope.tenantId,
          storage_provider: "LOCAL",
          original_filename: "passport.pdf",
          content_type: "application/pdf",
          size_bytes: 3,
          sha256: null,
          status: "READY",
          created_by_user_id: session.data.user.id,
          created_at: "2026-03-01T10:00:00Z",
          updated_at: "2026-03-01T10:00:00Z",
          meta: null,
        },
      }),
    });
  });

  await page.route(`**/api/v1/dms/files/${fileId}`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        data: {
          id: fileId,
          tenant_id: scope.tenantId,
          storage_provider: "LOCAL",
          original_filename: "passport.pdf",
          content_type: "application/pdf",
          size_bytes: 3,
          sha256: null,
          status: "READY",
          created_by_user_id: session.data.user.id,
          created_at: "2026-03-01T10:00:00Z",
          updated_at: "2026-03-01T10:00:00Z",
          meta: null,
        },
      }),
    });
  });

  await page.route(`**/api/v1/dms/files/${fileId}/download`, async (route) => {
    downloadCount += 1;
    await route.fulfill({
      status: 200,
      contentType: "application/pdf",
      headers: {
        "Content-Disposition": 'attachment; filename="passport.pdf"',
      },
      body: "pdf",
    });
  });

  await page.route(`**/api/v1/dms/documents/${documentId}/verify-request`, async (route) => {
    verificationRequested = true;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        data: { workflow_request_id: workflowRequestId },
      }),
    });
  });

  await page.route(`**/api/v1/workflow/requests/${workflowRequestId}`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        data: {
          request: {
            id: workflowRequestId,
            request_type_code: "DOCUMENT_VERIFICATION",
            status: approved ? "APPROVED" : "PENDING",
            current_step: 0,
            subject: "Verify passport",
            payload: {
              document_id: documentId,
              document_type_code: "PASSPORT",
              expires_at: "2026-12-31",
            },
            tenant_id: scope.tenantId,
            company_id: scope.companyId,
            branch_id: scope.branchId,
            created_by_user_id: session.data.user.id,
            requester_employee_id: employeeId,
            subject_employee_id: employeeId,
            entity_type: "dms.document",
            entity_id: documentId,
            created_at: "2026-03-01T10:00:00Z",
            updated_at: approved ? "2026-03-02T10:00:00Z" : "2026-03-01T10:00:00Z",
          },
          steps: [],
          comments: [],
          attachments: [],
          events: [],
        },
      }),
    });
  });

  await page.route(`**/api/v1/workflow/requests/${workflowRequestId}/approve`, async (route) => {
    approved = true;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        data: { id: workflowRequestId, status: "APPROVED", current_step: 0 },
      }),
    });
  });

  return {
    employeeId,
    documentId,
    workflowRequestId,
    getDownloadCount: () => downloadCount,
  };
}

async function mockSessionForRosterPayables(page: import("@playwright/test").Page) {
  const scope = { tenantId: "t-1", companyId: "c-1", branchId: "b-1" };
  const employeeId = "30000000-0000-4000-8000-000000000001";
  const shiftId = "40000000-0000-4000-8000-000000000001";

  await seedScope(page, scope);

  const session = {
    ok: true,
    data: {
      user: { id: "u-rp-1", email: "hr@example.com", status: "ACTIVE" },
      roles: ["HR"],
      permissions: [
        "hr:employee:read",
        "roster:shift:read",
        "roster:shift:write",
        "roster:assignment:read",
        "roster:assignment:write",
        "attendance:payable:admin:read",
        "attendance:payable:recompute",
      ],
      scope: {
        tenant_id: scope.tenantId,
        company_id: scope.companyId,
        branch_id: scope.branchId,
        allowed_tenant_ids: [scope.tenantId],
        allowed_company_ids: [scope.companyId],
        allowed_branch_ids: [scope.branchId],
      },
    },
  };

  let shiftCreated = false;
  let assignmentCreated = false;
  let recomputed = false;

  await page.route("**/api/v1/auth/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(session),
    });
  });

  await page.route("**/api/v1/tenancy/companies", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        data: [
          {
            id: scope.companyId,
            tenant_id: scope.tenantId,
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

  await page.route("**/api/v1/hr/employees**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        data: {
          items: [
            {
              employee_id: employeeId,
              employee_code: "E0001",
              status: "ACTIVE",
              full_name: "Alice One",
              email: "alice@example.com",
              phone: null,
              branch_id: scope.branchId,
              org_unit_id: null,
              manager_employee_id: null,
              manager_name: null,
            },
          ],
          paging: { limit: 12, offset: 0, total: 1 },
        },
      }),
    });
  });

  await page.route(`**/api/v1/hr/employees/${employeeId}`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        data: {
          employee: {
            id: employeeId,
            person_id: "person-1",
            employee_code: "E0001",
            status: "ACTIVE",
            join_date: "2026-01-01",
            termination_date: null,
          },
          person: {
            id: "person-1",
            first_name: "Alice",
            last_name: "One",
            email: "alice@example.com",
            phone: null,
          },
          current_employment: null,
          manager: null,
          linked_user: null,
        },
      }),
    });
  });

  await page.route(`**/api/v1/roster/branches/${scope.branchId}/shifts**`, async (route) => {
    if (route.request().method() === "POST") {
      shiftCreated = true;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ok: true,
          data: {
            id: shiftId,
            tenant_id: scope.tenantId,
            branch_id: scope.branchId,
            code: "DAY",
            name: "Day Shift",
            start_time: "09:00:00",
            end_time: "18:00:00",
            break_minutes: 60,
            grace_minutes: 10,
            min_full_day_minutes: 480,
            is_active: true,
            expected_minutes: 480,
            created_by_user_id: session.data.user.id,
            created_at: "2026-03-01T10:00:00Z",
            updated_at: "2026-03-01T10:00:00Z",
          },
        }),
      });
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        data: shiftCreated
          ? [
              {
                id: shiftId,
                tenant_id: scope.tenantId,
                branch_id: scope.branchId,
                code: "DAY",
                name: "Day Shift",
                start_time: "09:00:00",
                end_time: "18:00:00",
                break_minutes: 60,
                grace_minutes: 10,
                min_full_day_minutes: 480,
                is_active: true,
                expected_minutes: 480,
                created_by_user_id: session.data.user.id,
                created_at: "2026-03-01T10:00:00Z",
                updated_at: "2026-03-01T10:00:00Z",
              },
            ]
          : [],
      }),
    });
  });

  await page.route(`**/api/v1/roster/employees/${employeeId}/assignments`, async (route) => {
    if (route.request().method() === "POST") {
      assignmentCreated = true;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ok: true,
          data: {
            id: "50000000-0000-4000-8000-000000000001",
            tenant_id: scope.tenantId,
            employee_id: employeeId,
            branch_id: scope.branchId,
            shift_template_id: shiftId,
            effective_from: "2026-01-01",
            effective_to: null,
            created_by_user_id: session.data.user.id,
            created_at: "2026-03-01T10:00:00Z",
            updated_at: "2026-03-01T10:00:00Z",
          },
        }),
      });
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        data: assignmentCreated
          ? [
              {
                id: "50000000-0000-4000-8000-000000000001",
                tenant_id: scope.tenantId,
                employee_id: employeeId,
                branch_id: scope.branchId,
                shift_template_id: shiftId,
                effective_from: "2026-01-01",
                effective_to: null,
                created_by_user_id: session.data.user.id,
                created_at: "2026-03-01T10:00:00Z",
                updated_at: "2026-03-01T10:00:00Z",
              },
            ]
          : [],
      }),
    });
  });

  await page.route("**/api/v1/attendance/admin/payable-days**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        data: {
          items: recomputed
            ? [
                {
                  day: "2026-01-01",
                  employee_id: employeeId,
                  branch_id: scope.branchId,
                  shift_template_id: shiftId,
                  day_type: "WORKDAY",
                  presence_status: "PRESENT",
                  expected_minutes: 480,
                  worked_minutes: 480,
                  payable_minutes: 480,
                  anomalies_json: null,
                  source_breakdown: null,
                  computed_at: "2026-03-02T10:00:00Z",
                },
              ]
            : [],
          next_cursor: null,
        },
      }),
    });
  });

  await page.route("**/api/v1/attendance/payable/recompute", async (route) => {
    recomputed = true;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ ok: true, data: { computed_rows: 1 } }),
    });
  });

  return { employeeId };
}

async function mockSessionForPayroll(page: import("@playwright/test").Page) {
  const scope = { tenantId: "t-1", companyId: "c-1", branchId: "b-1" };
  const payrunId = "70000000-0000-4000-8000-000000000001";
  const workflowRequestId = "70000000-0000-4000-8000-000000000002";
  const payslipId = "70000000-0000-4000-8000-000000000003";

  await seedScope(page, scope);

  const session = {
    ok: true,
    data: {
      user: { id: "u-payroll-1", email: "payroll@example.com", status: "ACTIVE" },
      roles: ["HR"],
      permissions: [
        "payroll:calendar:read",
        "payroll:payrun:read",
        "payroll:payrun:generate",
        "payroll:payrun:submit",
        "payroll:payrun:publish",
        "payroll:payrun:export",
        "payroll:payslip:read",
        "workflow:request:read",
        "workflow:request:approve",
      ],
      scope: {
        tenant_id: scope.tenantId,
        company_id: scope.companyId,
        branch_id: scope.branchId,
        allowed_tenant_ids: [scope.tenantId],
        allowed_company_ids: [scope.companyId],
        allowed_branch_ids: [scope.branchId],
      },
    },
  };

  let payrunStatus: "DRAFT" | "PENDING_APPROVAL" | "APPROVED" | "PUBLISHED" = "DRAFT";
  let workflowStatus: "PENDING" | "APPROVED" = "PENDING";
  let payslipDownloadCount = 0;

  await page.route("**/api/v1/auth/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(session),
    });
  });

  await page.route("**/api/v1/tenancy/companies", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        data: [
          {
            id: scope.companyId,
            tenant_id: scope.tenantId,
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

  await page.route("**/api/v1/payroll/calendars", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        data: [
          {
            id: "70000000-0000-4000-8000-000000000010",
            tenant_id: scope.tenantId,
            code: "MONTHLY",
            name: "Monthly Payroll",
            frequency: "MONTHLY",
            currency_code: "SAR",
            timezone: "Asia/Riyadh",
            is_active: true,
            created_by_user_id: null,
            created_at: "2026-03-01T10:00:00Z",
            updated_at: "2026-03-01T10:00:00Z",
          },
        ],
      }),
    });
  });

  await page.route("**/api/v1/payroll/calendars/*/periods**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        data: [
          {
            id: "70000000-0000-4000-8000-000000000011",
            tenant_id: scope.tenantId,
            calendar_id: "70000000-0000-4000-8000-000000000010",
            period_key: "2026-03",
            start_date: "2026-03-01",
            end_date: "2026-03-31",
            status: "OPEN",
            created_at: "2026-03-01T10:00:00Z",
            updated_at: "2026-03-01T10:00:00Z",
          },
        ],
      }),
    });
  });

  await page.route("**/api/v1/payroll/payruns/generate", async (route) => {
    payrunStatus = "DRAFT";
    workflowStatus = "PENDING";
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        data: {
          id: payrunId,
          tenant_id: scope.tenantId,
          calendar_id: "70000000-0000-4000-8000-000000000010",
          period_id: "70000000-0000-4000-8000-000000000011",
          branch_id: scope.branchId,
          version: 1,
          status: payrunStatus,
          generated_at: "2026-03-01T10:00:00Z",
          generated_by_user_id: null,
          workflow_request_id: null,
          idempotency_key: "payrun:test",
          totals_json: {
            included_count: 1,
            excluded_count: 0,
            gross_total: "5000.00",
            deductions_total: "0.00",
            net_total: "5000.00",
            currency_code: "SAR",
            computed_at: "2026-03-01T10:00:00Z",
          },
          created_at: "2026-03-01T10:00:00Z",
          updated_at: "2026-03-01T10:00:00Z",
        },
      }),
    });
  });

  await page.route(`**/api/v1/payroll/payruns/${payrunId}?**`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        data: {
          payrun: {
            id: payrunId,
            tenant_id: scope.tenantId,
            calendar_id: "70000000-0000-4000-8000-000000000010",
            period_id: "70000000-0000-4000-8000-000000000011",
            branch_id: scope.branchId,
            version: 1,
            status: payrunStatus,
            generated_at: "2026-03-01T10:00:00Z",
            generated_by_user_id: null,
            workflow_request_id: payrunStatus === "DRAFT" ? null : workflowRequestId,
            idempotency_key: "payrun:test",
            totals_json: {
              included_count: 1,
              excluded_count: 0,
              gross_total: "5000.00",
              deductions_total: "0.00",
              net_total: "5000.00",
              currency_code: "SAR",
              computed_at: "2026-03-01T10:00:00Z",
            },
            created_at: "2026-03-01T10:00:00Z",
            updated_at: "2026-03-01T10:00:00Z",
          },
          items: [
            {
              id: "70000000-0000-4000-8000-000000000020",
              tenant_id: scope.tenantId,
              payrun_id: payrunId,
              employee_id: "employee-1",
              payable_days: 31,
              payable_minutes: 14880,
              working_days_in_period: 31,
              gross_amount: "5000.00",
              deductions_amount: "0.00",
              net_amount: "5000.00",
              status: "INCLUDED",
              computed_json: { base_amount: "5000.00" },
              anomalies_json: null,
              created_at: "2026-03-01T10:00:00Z",
            },
          ],
          lines: [
            {
              id: "70000000-0000-4000-8000-000000000021",
              tenant_id: scope.tenantId,
              payrun_item_id: "70000000-0000-4000-8000-000000000020",
              component_id: "component-1",
              component_code: "BASIC",
              component_type: "EARNING",
              amount: "5000.00",
              meta_json: null,
              created_at: "2026-03-01T10:00:00Z",
            },
          ],
        },
      }),
    });
  });

  await page.route(`**/api/v1/payroll/payruns/${payrunId}/submit-approval`, async (route) => {
    payrunStatus = "PENDING_APPROVAL";
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        data: {
          payrun_id: payrunId,
          workflow_request_id: workflowRequestId,
          status: payrunStatus,
        },
      }),
    });
  });

  await page.route(`**/api/v1/workflow/requests/${workflowRequestId}`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        data: {
          request: {
            id: workflowRequestId,
            request_type_code: "PAYRUN_APPROVAL",
            status: workflowStatus,
            current_step: 0,
            subject: "Approve March payroll",
            payload: { payrun_id: payrunId, period_key: "2026-03", branch_id: scope.branchId },
            tenant_id: scope.tenantId,
            company_id: scope.companyId,
            branch_id: scope.branchId,
            created_by_user_id: session.data.user.id,
            requester_employee_id: null,
            subject_employee_id: null,
            entity_type: "payroll.payrun",
            entity_id: payrunId,
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

  await page.route(`**/api/v1/workflow/requests/${workflowRequestId}/approve`, async (route) => {
    workflowStatus = "APPROVED";
    payrunStatus = "APPROVED";
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ ok: true, data: { id: workflowRequestId, status: "APPROVED", current_step: 0 } }),
    });
  });

  await page.route(`**/api/v1/payroll/payruns/${payrunId}/publish`, async (route) => {
    payrunStatus = "PUBLISHED";
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        data: { payrun_id: payrunId, published_count: 1, status: payrunStatus },
      }),
    });
  });

  await page.route("**/api/v1/ess/me/payslips**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        data: {
          items:
            payrunStatus === "PUBLISHED"
              ? [
                  {
                    id: payslipId,
                    tenant_id: scope.tenantId,
                    payrun_id: payrunId,
                    employee_id: "employee-1",
                    status: "PUBLISHED",
                    dms_document_id: "doc-1",
                    period_key: "2026-03",
                    created_at: "2026-03-01T10:00:00Z",
                    updated_at: "2026-03-01T10:00:00Z",
                  },
                ]
              : [],
        },
      }),
    });
  });

  await page.route(`**/api/v1/ess/me/payslips/${payslipId}/download`, async (route) => {
    payslipDownloadCount += 1;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      headers: {
        "Content-Disposition": 'attachment; filename="payslip_2026-03.json"',
      },
      body: JSON.stringify({ payslip_id: payslipId, period_key: "2026-03" }),
    });
  });

  return { payrunId, workflowRequestId, payslipId, getPayslipDownloadCount: () => payslipDownloadCount };
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

test.describe("dms (mocked)", () => {
  test.skip(({ browserName }) => browserName !== "chromium", "chromium-only");

  test("employee document verification flow", async ({ page }) => {
    const dms = await mockSessionForDms(page);

    await page.goto(`/dms/employee-docs?employeeId=${dms.employeeId}`);
    await expect(page.getByRole("heading", { name: /employee docs/i })).toBeVisible();

    await page.getByRole("button", { name: /upload doc/i }).click();
    await page.selectOption("#dms-upload-type", "PASSPORT");
    await page.setInputFiles("#dms-upload-file", {
      name: "passport.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from("pdf"),
    });
    await page.getByRole("button", { name: /^upload$/i }).click();

    await expect(page.getByRole("button", { name: /request verification/i })).toBeVisible();
    await page.getByRole("button", { name: /request verification/i }).click();

    await expect(page).toHaveURL(new RegExp(`/workflow/requests/${dms.workflowRequestId}$`));
    await expect(page.getByRole("link", { name: "Open document" })).toBeVisible();

    await page.getByRole("button", { name: /^approve$/i }).click();

    await page.goto(`/dms/employee-docs?employeeId=${dms.employeeId}&docId=${dms.documentId}`);
    await expect(page.getByText("VERIFIED")).toBeVisible();

    await page.getByRole("button", { name: /download current document/i }).click();
    await expect.poll(() => dms.getDownloadCount()).toBe(1);
  });
});

test.describe("roster + payables (mocked)", () => {
  test.skip(({ browserName }) => browserName !== "chromium", "chromium-only");

  test("create shift, assign employee, recompute payables", async ({ page }) => {
    const roster = await mockSessionForRosterPayables(page);

    await page.goto("/roster/shifts");
    await expect(page.getByRole("heading", { name: /shift templates/i })).toBeVisible();
    await page.getByRole("button", { name: /create shift/i }).click();
    await page.locator("#create-shift-code").fill("DAY");
    await page.locator("#create-shift-name").fill("Day Shift");
    await page.getByRole("button", { name: /^create shift$/i }).last().click();
    await expect(page.getByText("Day Shift")).toBeVisible();

    await page.goto(`/roster/assignments?employeeId=${roster.employeeId}`);
    await expect(page.getByRole("heading", { name: /shift assignments/i })).toBeVisible();
    await page.getByRole("button", { name: /create assignment/i }).click();
    await page.locator("#assignment-from").fill("2026-01-01");
    await page.getByRole("button", { name: /^create assignment$/i }).last().click();
    await expect(page.getByText("2026-01-01")).toBeVisible();

    await page.goto("/payables/admin");
    await expect(page.getByRole("heading", { name: /payables admin/i })).toBeVisible();
    await page.getByRole("button", { name: /^recompute$/i }).click();
    await expect(page.getByText("2026-01-01")).toBeVisible();
  });
});

test.describe("payroll (mocked)", () => {
  test.skip(({ browserName }) => browserName !== "chromium", "chromium-only");

  test("generate, approve, publish, and expose payslip", async ({ page }) => {
    const payroll = await mockSessionForPayroll(page);

    await page.goto("/payroll/payruns");
    await expect(page.getByRole("heading", { name: /payruns/i })).toBeVisible();

    await page.getByRole("button", { name: /generate payrun/i }).click();
    await page.selectOption("#payrun-calendar", "70000000-0000-4000-8000-000000000010");
    await page.selectOption("#payrun-period", "2026-03");
    await page.getByRole("button", { name: /^generate payrun$/i }).last().click();

    await expect(page).toHaveURL(new RegExp(`/payroll/payruns/${payroll.payrunId}$`));
    await expect(page.getByRole("button", { name: /submit for approval/i })).toBeVisible();
    await page.getByRole("button", { name: /submit for approval/i }).click();

    await expect(page.getByRole("link", { name: /open approval request/i })).toBeVisible();
    await page.goto(`/workflow/requests/${payroll.workflowRequestId}`);
    await expect(page.getByRole("link", { name: /open payrun/i })).toBeVisible();
    await page.getByRole("button", { name: /^approve$/i }).click();

    await page.goto(`/payroll/payruns/${payroll.payrunId}`);
    await expect(page.getByRole("button", { name: /^publish$/i })).toBeEnabled();
    await page.getByRole("button", { name: /^publish$/i }).click();
    await expect(page.getByText(/status published/i)).toBeVisible();

    await page.goto(`/ess/payslips?year=2026&payslipId=${payroll.payslipId}`);
    await expect(page.getByRole("heading", { name: /payslips/i })).toBeVisible();
    await expect(page.getByText("2026-03")).toBeVisible();
    await page.getByRole("button", { name: /download payslip/i }).click();
    await expect.poll(() => payroll.getPayslipDownloadCount()).toBe(1);
  });
});
