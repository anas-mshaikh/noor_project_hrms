import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { fireEvent, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ymdFromDateLocal } from "@/lib/dateRange";
import type {
  AttendanceDaysOut,
  AttendanceCorrectionOut,
  LeaveBalancesOut,
  LeaveRequestListOut,
  LeaveRequestOut,
  MeResponse,
  TeamCalendarOut,
  WorkflowRequestDetailOut,
  WorkflowRequestListOut,
  WorkflowRequestSummaryOut,
} from "@/lib/types";
import { ok } from "@/test/msw/builders/response";
import { server } from "@/test/msw/server";
import { renderWithProviders } from "@/test/utils/render";
import { setPathname, setSearchParams } from "@/test/utils/router";
import { seedScope, seedSession } from "@/test/utils/selection";

import AttendanceDaysPage from "@/app/attendance/days/page";
import AttendanceCorrectionNewPage from "@/app/attendance/corrections/new/page";
import LeavePage from "@/app/leave/page";
import LeaveTeamCalendarPage from "@/app/leave/team-calendar/page";
import WorkflowInboxPage from "@/app/workflow/inbox/page";

const TENANT_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const COMPANY_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
const BRANCH_ID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc";

function baseScope() {
  return {
    tenant_id: TENANT_ID,
    company_id: COMPANY_ID,
    branch_id: BRANCH_ID,
    allowed_tenant_ids: [TENANT_ID],
    allowed_company_ids: [COMPANY_ID],
    allowed_branch_ids: [BRANCH_ID],
  };
}

describe("M6 stories (workflow-integrated)", () => {
  it("attendance correction: employee submits -> manager approves -> days reflect override", async () => {
    const now = new Date();
    const DAY = ymdFromDateLocal(new Date(now.getFullYear(), now.getMonth(), 1));

    const CORR_ID = "11111111-1111-4111-8111-111111111111";
    const WF_ID = "22222222-2222-4222-8222-222222222222";

    let approved = false;

    // Attendance endpoints.
    server.use(
      http.get("*/api/v1/attendance/me/days", () => {
        const out: AttendanceDaysOut = {
          items: approved
            ? [
                {
                  day: DAY,
                  base_status: "ABSENT",
                  effective_status: "PRESENT_OVERRIDE",
                  base_minutes: 0,
                  effective_minutes: 480,
                  first_in: null,
                  last_out: null,
                  has_open_session: false,
                  sources: ["CORRECTION"],
                  override: {
                    kind: "CORRECTION",
                    status: "PRESENT_OVERRIDE",
                    source_type: "ATTENDANCE_CORRECTION",
                    source_id: CORR_ID,
                  },
                },
              ]
            : [
                {
                  day: DAY,
                  base_status: "ABSENT",
                  effective_status: "ABSENT",
                  base_minutes: 0,
                  effective_minutes: 0,
                  first_in: null,
                  last_out: null,
                  has_open_session: false,
                  sources: ["BASE"],
                  override: null,
                },
              ],
        };
        return HttpResponse.json(ok(out));
      }),

      http.post("*/api/v1/attendance/me/corrections", async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        expect(body.day).toBe(DAY);
        expect(body.correction_type).toBe("MARK_PRESENT");

        const out: AttendanceCorrectionOut = {
          id: CORR_ID,
          tenant_id: TENANT_ID,
          employee_id: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
          branch_id: BRANCH_ID,
          day: DAY,
          correction_type: "MARK_PRESENT",
          requested_override_status: "PRESENT_OVERRIDE",
          reason: String(body.reason ?? "reason"),
          evidence_file_ids: [],
          status: "PENDING",
          workflow_request_id: WF_ID,
          idempotency_key: String(body.idempotency_key ?? ""),
          created_at: new Date(0).toISOString(),
          updated_at: new Date(0).toISOString(),
        };
        return HttpResponse.json(ok(out));
      })
    );

    // Workflow endpoints (manager approves).
    server.use(
      http.get("*/api/v1/workflow/inbox", () => {
        const item: WorkflowRequestSummaryOut = {
          id: WF_ID,
          request_type_code: "ATTENDANCE_CORRECTION",
          status: approved ? "APPROVED" : "PENDING",
          current_step: 0,
          subject: `Attendance correction ${DAY}`,
          payload: { day: DAY, correction_id: CORR_ID },
          tenant_id: TENANT_ID,
          company_id: COMPANY_ID,
          branch_id: BRANCH_ID,
          created_by_user_id: null,
          requester_employee_id: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
          subject_employee_id: null,
          entity_type: "attendance.attendance_correction",
          entity_id: CORR_ID,
          created_at: new Date(0).toISOString(),
          updated_at: new Date(0).toISOString(),
        };

        const out: WorkflowRequestListOut = {
          items: approved ? [] : [item],
          next_cursor: null,
        };
        return HttpResponse.json(ok(out));
      }),

      http.get("*/api/v1/workflow/requests/:id", ({ params }) => {
        expect(String(params.id)).toBe(WF_ID);
        const req: WorkflowRequestSummaryOut = {
          id: WF_ID,
          request_type_code: "ATTENDANCE_CORRECTION",
          status: approved ? "APPROVED" : "PENDING",
          current_step: approved ? 1 : 0,
          subject: `Attendance correction ${DAY}`,
          payload: { day: DAY, correction_id: CORR_ID },
          tenant_id: TENANT_ID,
          company_id: COMPANY_ID,
          branch_id: BRANCH_ID,
          created_by_user_id: null,
          requester_employee_id: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
          subject_employee_id: null,
          entity_type: "attendance.attendance_correction",
          entity_id: CORR_ID,
          created_at: new Date(0).toISOString(),
          updated_at: new Date(0).toISOString(),
        };
        const out: WorkflowRequestDetailOut = {
          request: req,
          steps: [],
          comments: [],
          attachments: [],
          events: [],
        };
        return HttpResponse.json(ok(out));
      }),

      http.post("*/api/v1/workflow/requests/:id/approve", ({ params }) => {
        expect(String(params.id)).toBe(WF_ID);
        approved = true;
        return HttpResponse.json(ok({ id: WF_ID, status: "APPROVED", current_step: 1 }));
      })
    );

    const EMP: MeResponse = {
      user: { id: "u-emp", email: "employee@example.com", status: "ACTIVE" },
      roles: ["EMPLOYEE"],
      permissions: ["attendance:correction:read", "attendance:correction:submit"],
      scope: baseScope(),
    };

    const MGR: MeResponse = {
      user: { id: "u-mgr", email: "manager@example.com", status: "ACTIVE" },
      roles: ["MANAGER"],
      permissions: ["workflow:request:read", "workflow:request:approve"],
      scope: baseScope(),
    };

    // Employee sees the day as ABSENT.
    seedSession(EMP);
    seedScope({ tenantId: TENANT_ID, companyId: COMPANY_ID, branchId: BRANCH_ID });
    setPathname("/attendance/days");
    const days1 = renderWithProviders(<AttendanceDaysPage />);
    expect(await screen.findByText(DAY)).toBeVisible();
    expect(screen.getByText("ABSENT")).toBeVisible();
    days1.unmount();

    // Employee submits a correction for that day.
    seedSession(EMP);
    setPathname("/attendance/corrections/new");
    setSearchParams({ day: DAY });
    const corr = renderWithProviders(<AttendanceCorrectionNewPage />);
    fireEvent.change(screen.getByLabelText("Reason"), { target: { value: "missed punch" } });
    fireEvent.click(screen.getByRole("button", { name: "Submit" }));
    expect(await screen.findByRole("link", { name: "View request" })).toHaveAttribute(
      "href",
      `/workflow/requests/${WF_ID}`
    );
    corr.unmount();

    // Manager approves in workflow inbox.
    seedSession(MGR);
    setPathname("/workflow/inbox");
    setSearchParams({});
    const inbox = renderWithProviders(<WorkflowInboxPage />);
    fireEvent.click(await screen.findByRole("button", { name: /ATTENDANCE_CORRECTION/i }));
    fireEvent.click(await screen.findByRole("button", { name: "Approve" }));
    expect(await screen.findByText("No requests")).toBeVisible();
    inbox.unmount();

    // Employee days now reflect the override.
    seedSession(EMP);
    setPathname("/attendance/days");
    const days2 = renderWithProviders(<AttendanceDaysPage />);
    expect(await screen.findByText(DAY)).toBeVisible();
    expect(await screen.findByText("PRESENT_OVERRIDE")).toBeVisible();
    expect(await screen.findByText("8h 00m")).toBeVisible();
    days2.unmount();
  });

  it("leave: employee applies -> manager approves -> balances/requests/calendar reflect approval", async () => {
    const user = userEvent.setup();
    const now = new Date();
    const START = ymdFromDateLocal(new Date(now.getFullYear(), now.getMonth(), 10));
    const END = ymdFromDateLocal(new Date(now.getFullYear(), now.getMonth(), 12));

    const LEAVE_ID = "33333333-3333-4333-8333-333333333333";
    const WF_ID = "44444444-4444-4444-8444-444444444444";

    let leaveStatus: "NONE" | "PENDING" | "APPROVED" = "NONE";

    function balances(): LeaveBalancesOut {
      const pending = leaveStatus === "PENDING" ? 3 : 0;
      const used = leaveStatus === "APPROVED" ? 3 : 0;
      // Keep it simple: balance_days reflects remaining.
      const balance = 10 - used;
      return {
        items: [
          {
            leave_type_code: "AL",
            leave_type_name: "Annual Leave",
            period_year: now.getFullYear(),
            balance_days: balance,
            used_days: used,
            pending_days: pending,
          },
        ],
      };
    }

    function leaveRequest(): LeaveRequestOut {
      return {
        id: LEAVE_ID,
        tenant_id: TENANT_ID,
        employee_id: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
        company_id: COMPANY_ID,
        branch_id: BRANCH_ID,
        leave_type_code: "AL",
        leave_type_name: "Annual Leave",
        policy_id: "55555555-5555-4555-8555-555555555555",
        start_date: START,
        end_date: END,
        unit: "DAY",
        half_day_part: null,
        requested_days: 3,
        reason: null,
        status: leaveStatus === "APPROVED" ? "APPROVED" : "PENDING",
        workflow_request_id: WF_ID,
        created_at: new Date(0).toISOString(),
        updated_at: new Date(0).toISOString(),
      };
    }

    server.use(
      http.get("*/api/v1/leave/me/balances", () => HttpResponse.json(ok(balances()))),
      http.get("*/api/v1/leave/me/requests", () => {
        const out: LeaveRequestListOut = {
          items: leaveStatus === "NONE" ? [] : [leaveRequest()],
          next_cursor: null,
        };
        return HttpResponse.json(ok(out));
      }),
      http.post("*/api/v1/leave/me/requests", async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        expect(body.leave_type_code).toBe("AL");
        expect(body.start_date).toBe(START);
        expect(body.end_date).toBe(END);
        leaveStatus = "PENDING";
        return HttpResponse.json(ok(leaveRequest()));
      }),
      http.get("*/api/v1/leave/team/calendar", ({ request }) => {
        // Team calendar shows APPROVED only.
        const url = new URL(request.url);
        const from = url.searchParams.get("from") ?? START;
        const out: TeamCalendarOut = {
          items:
            leaveStatus === "APPROVED"
              ? [
                  {
                    leave_request_id: LEAVE_ID,
                    employee_id: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
                    start_date: from,
                    end_date: from,
                    leave_type_code: "AL",
                    requested_days: 1,
                  },
                ]
              : [],
        };
        return HttpResponse.json(ok(out));
      })
    );

    // Workflow endpoints.
    server.use(
      http.get("*/api/v1/workflow/inbox", () => {
        const item: WorkflowRequestSummaryOut = {
          id: WF_ID,
          request_type_code: "LEAVE_REQUEST",
          status: leaveStatus === "APPROVED" ? "APPROVED" : "PENDING",
          current_step: 0,
          subject: `Leave request ${LEAVE_ID.slice(0, 8)}…`,
          payload: { leave_request_id: LEAVE_ID, leave_type_code: "AL", start_date: START, end_date: END },
          tenant_id: TENANT_ID,
          company_id: COMPANY_ID,
          branch_id: BRANCH_ID,
          created_by_user_id: null,
          requester_employee_id: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
          subject_employee_id: null,
          entity_type: "leave.leave_request",
          entity_id: LEAVE_ID,
          created_at: new Date(0).toISOString(),
          updated_at: new Date(0).toISOString(),
        };
        const out: WorkflowRequestListOut = {
          items: leaveStatus === "APPROVED" ? [] : leaveStatus === "NONE" ? [] : [item],
          next_cursor: null,
        };
        return HttpResponse.json(ok(out));
      }),
      http.get("*/api/v1/workflow/requests/:id", ({ params }) => {
        expect(String(params.id)).toBe(WF_ID);
        const req: WorkflowRequestSummaryOut = {
          id: WF_ID,
          request_type_code: "LEAVE_REQUEST",
          status: leaveStatus === "APPROVED" ? "APPROVED" : "PENDING",
          current_step: leaveStatus === "APPROVED" ? 1 : 0,
          subject: `Leave request ${LEAVE_ID.slice(0, 8)}…`,
          payload: { leave_request_id: LEAVE_ID, leave_type_code: "AL", start_date: START, end_date: END },
          tenant_id: TENANT_ID,
          company_id: COMPANY_ID,
          branch_id: BRANCH_ID,
          created_by_user_id: null,
          requester_employee_id: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
          subject_employee_id: null,
          entity_type: "leave.leave_request",
          entity_id: LEAVE_ID,
          created_at: new Date(0).toISOString(),
          updated_at: new Date(0).toISOString(),
        };
        const out: WorkflowRequestDetailOut = {
          request: req,
          steps: [],
          comments: [],
          attachments: [],
          events: [],
        };
        return HttpResponse.json(ok(out));
      }),
      http.post("*/api/v1/workflow/requests/:id/approve", ({ params }) => {
        expect(String(params.id)).toBe(WF_ID);
        leaveStatus = "APPROVED";
        return HttpResponse.json(ok({ id: WF_ID, status: "APPROVED", current_step: 1 }));
      })
    );

    const EMP: MeResponse = {
      user: { id: "u-emp", email: "employee@example.com", status: "ACTIVE" },
      roles: ["EMPLOYEE"],
      permissions: ["leave:balance:read", "leave:request:read", "leave:request:submit"],
      scope: baseScope(),
    };

    const MGR: MeResponse = {
      user: { id: "u-mgr", email: "manager@example.com", status: "ACTIVE" },
      roles: ["MANAGER"],
      permissions: ["workflow:request:read", "workflow:request:approve", "leave:team:read"],
      scope: baseScope(),
    };

    // Employee applies leave.
    seedSession(EMP);
    seedScope({ tenantId: TENANT_ID, companyId: COMPANY_ID, branchId: BRANCH_ID });
    setPathname("/leave");
    const leave1 = renderWithProviders(<LeavePage />);

    // Wait for balances to load; apply is disabled until leave types are available.
    expect(await screen.findByText("Annual Leave")).toBeVisible();
    const applyBtn = await screen.findByRole("button", { name: "Apply leave" });
    expect(applyBtn).not.toBeDisabled();
    await user.click(applyBtn);
    await user.selectOptions(screen.getByLabelText("Leave type"), "AL");
    await user.type(screen.getByLabelText("Start"), START);
    await user.type(screen.getByLabelText("End"), END);
    await user.click(screen.getByRole("button", { name: "Submit request" }));

    // The apply flow invalidates balances; pending should appear.
    expect(await screen.findByText("pending 3")).toBeVisible();

    leave1.unmount();

    // Manager approves in workflow inbox.
    seedSession(MGR);
    seedScope({ tenantId: TENANT_ID, companyId: COMPANY_ID, branchId: BRANCH_ID });
    setPathname("/workflow/inbox");
    setSearchParams({});
    const inbox = renderWithProviders(<WorkflowInboxPage />);
    await user.click(await screen.findByRole("button", { name: /LEAVE_REQUEST/i }));
    await user.click(await screen.findByRole("button", { name: "Approve" }));
    expect(await screen.findByText("No requests")).toBeVisible();
    inbox.unmount();

    // Employee sees request approved + balances updated.
    seedSession(EMP);
    seedScope({ tenantId: TENANT_ID, companyId: COMPANY_ID, branchId: BRANCH_ID });
    setPathname("/leave");
    const leave2 = renderWithProviders(<LeavePage />);
    expect(await screen.findByText("APPROVED")).toBeVisible();
    expect(await screen.findByText("pending 0")).toBeVisible();
    leave2.unmount();

    // Manager team calendar reflects the approved leave (spans only after approval).
    seedSession(MGR);
    seedScope({ tenantId: TENANT_ID, companyId: COMPANY_ID, branchId: BRANCH_ID });
    setPathname("/leave/team-calendar");
    const cal = renderWithProviders(<LeaveTeamCalendarPage />);
    expect(await screen.findByRole("heading", { name: "Team Calendar" })).toBeVisible();
    expect(await screen.findByText("AL (1)")).toBeVisible();
    cal.unmount();
  }, 30_000);
});
