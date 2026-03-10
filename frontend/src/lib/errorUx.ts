import { ApiError } from "@/lib/api";

export type SuggestedActionKind =
  | "none"
  | "retry"
  | "go_login"
  | "go_scope"
  | "reset_scope";

export type ErrorUx = {
  title: string;
  description: string;
  suggestedActionKind: SuggestedActionKind;
};

function isScopeCode(code: string): boolean {
  return code.startsWith("iam.scope.");
}

/**
 * Map stable backend error codes into friendly UI copy and recovery guidance.
 *
 * Keep this conservative: unknown codes should fall back to a generic message
 * while still surfacing the correlation id for support.
 */
export function getErrorUx(err: unknown): ErrorUx {
  if (err instanceof ApiError) {
    if (err.isNetworkError || err.code === "network_error" || err.status === 0) {
      return {
        title: "Network error",
        description: "Could not reach the server. Check your connection and try again.",
        suggestedActionKind: "retry",
      };
    }

    if (err.status === 401 || err.code.startsWith("unauthorized")) {
      return {
        title: "Session expired",
        description: "Please sign in again.",
        suggestedActionKind: "go_login",
      };
    }

    if (isScopeCode(err.code)) {
      if (err.code === "iam.scope.tenant_required") {
        return {
          title: "Tenant selection required",
          description:
            "Your account can access multiple tenants. Select the tenant/company/branch you want to work in.",
          suggestedActionKind: "go_scope",
        };
      }

      // Covers forbidden/mismatch/invalid company/branch/tenant etc.
      return {
        title: "Scope not allowed",
        description:
          "Your current selection is not covered by your role assignments. Re-select your tenant/company/branch and try again.",
        suggestedActionKind: "reset_scope",
      };
    }

    if (err.code === "ess.not_linked") {
      return {
        title: "Account not linked",
        description: "Your user account is not linked to an employee profile yet. Contact HR to link your account.",
        suggestedActionKind: "none",
      };
    }

    if (err.code === "mss.not_linked") {
      return {
        title: "Account not linked",
        description: "Your user account is not linked to an employee profile yet. Contact HR to enable manager access.",
        suggestedActionKind: "none",
      };
    }

    if (err.code === "mss.no_current_employment") {
      return {
        title: "No current employment",
        description: "Your employee profile does not have a current employment record. Contact HR for assistance.",
        suggestedActionKind: "none",
      };
    }

    if (err.code === "mss.forbidden_employee") {
      return {
        title: "Not allowed",
        description: "You do not have access to this team member.",
        suggestedActionKind: "none",
      };
    }

    // Bootstrap is allowed only on a fresh DB; show a clearer message than a
    // generic 409 "Conflict".
    if (err.code === "already_bootstrapped") {
      return {
        title: "Already configured",
        description:
          "This environment is already configured. Sign in to continue, or choose a different tenant/company/branch if you have access.",
        suggestedActionKind: "go_login",
      };
    }

    if (err.code === "hr.employee.code_exists") {
      return {
        title: "Employee code already exists",
        description: "Choose a unique employee code and try again.",
        suggestedActionKind: "none",
      };
    }

    if (err.code === "hr.branch.invalid") {
      return {
        title: "Invalid branch",
        description: "The selected branch is not part of the active company scope.",
        suggestedActionKind: "none",
      };
    }

    if (err.code === "hr.manager.cycle") {
      return {
        title: "Invalid manager assignment",
        description: "This change would create a reporting cycle. Select a different manager and try again.",
        suggestedActionKind: "none",
      };
    }

    if (err.code.startsWith("hr.employee_user_link.")) {
      return {
        title: "Link conflict",
        description:
          "This employee or user is already linked. If you believe this is wrong, contact an administrator.",
        suggestedActionKind: "none",
      };
    }

    // ----- Attendance (ESS) -----
    if (err.code === "attendance.correction.too_old") {
      return {
        title: "Correction window closed",
        description: "This day is too old to correct. Contact HR if you need an exception.",
        suggestedActionKind: "none",
      };
    }

    if (err.code === "attendance.correction.future_not_allowed") {
      return {
        title: "Future correction not allowed",
        description: "You cannot submit a correction for a future day.",
        suggestedActionKind: "none",
      };
    }

    if (err.code === "attendance.correction.reason_required") {
      return {
        title: "Reason required",
        description: "Add a reason and try again.",
        suggestedActionKind: "none",
      };
    }

    if (err.code === "attendance.correction.conflict.leave") {
      return {
        title: "Cannot correct a leave day",
        description: "This day is on leave and cannot be corrected.",
        suggestedActionKind: "none",
      };
    }

    if (err.code === "attendance.correction.pending_exists") {
      return {
        title: "Correction already pending",
        description: "A pending correction already exists for this day.",
        suggestedActionKind: "none",
      };
    }

    if (err.code === "attendance.correction.idempotency.conflict") {
      return {
        title: "Duplicate submission",
        description: "This idempotency key was already used with a different correction payload.",
        suggestedActionKind: "none",
      };
    }

    if (err.code === "attendance.punch.disabled") {
      return {
        title: "Punching disabled",
        description: "Punching is disabled for this branch. Contact HR for assistance.",
        suggestedActionKind: "none",
      };
    }

    if (err.code === "attendance.punch.already_in") {
      return {
        title: "Already punched in",
        description: "You are already punched in. Punch out to close your current session.",
        suggestedActionKind: "none",
      };
    }

    if (err.code === "attendance.punch.not_in") {
      return {
        title: "Not punched in",
        description: "You are not currently punched in.",
        suggestedActionKind: "none",
      };
    }

    if (err.code === "attendance.punch.conflict.leave") {
      return {
        title: "Cannot punch on leave",
        description: "You cannot punch in on a day that is on leave.",
        suggestedActionKind: "none",
      };
    }

    if (err.code === "attendance.punch.multiple_sessions_not_allowed") {
      return {
        title: "Multiple sessions not allowed",
        description: "This branch does not allow multiple work sessions in a single day.",
        suggestedActionKind: "none",
      };
    }

    // ----- Leave (ESS/MSS) -----
    if (err.code === "leave.overlap") {
      return {
        title: "Overlapping leave",
        description: "This leave request overlaps with an existing request.",
        suggestedActionKind: "none",
      };
    }

    if (err.code === "leave.insufficient_balance") {
      return {
        title: "Insufficient balance",
        description: "You do not have enough leave balance for this request.",
        suggestedActionKind: "none",
      };
    }

    if (err.code === "leave.policy.missing") {
      return {
        title: "Leave policy missing",
        description: "Your employee profile is missing leave policy configuration. Contact HR for help.",
        suggestedActionKind: "none",
      };
    }

    if (err.code === "leave.policy.rule.missing") {
      return {
        title: "Leave type not allowed",
        description: "This leave type is not allowed under your policy. Contact HR for help.",
        suggestedActionKind: "none",
      };
    }

    if (err.code === "leave.calendar.missing") {
      return {
        title: "Leave calendar not configured",
        description: "Weekly off / holiday calendar is missing for your branch. Contact HR to configure it.",
        suggestedActionKind: "none",
      };
    }

    if (err.code === "leave.attachment_required") {
      return {
        title: "Attachment required",
        description: "This leave type requires an attachment. Add an attachment and try again.",
        suggestedActionKind: "none",
      };
    }

    if (err.code === "leave.half_day.invalid") {
      return {
        title: "Invalid half-day request",
        description: "Half-day leave must be for a single day and requires selecting AM or PM.",
        suggestedActionKind: "none",
      };
    }

    if (err.code === "leave.invalid_range") {
      return {
        title: "Invalid date range",
        description: "Check the selected dates and try again.",
        suggestedActionKind: "none",
      };
    }

    // ----- Roster -----
    if (err.code === "roster.shift.invalid_time_range") {
      return {
        title: "Invalid shift time range",
        description: "End time cannot equal the start time. Adjust the shift times and try again.",
        suggestedActionKind: "none",
      };
    }

    if (err.code === "roster.shift.break_invalid") {
      return {
        title: "Invalid break duration",
        description: "Break minutes must be smaller than the shift duration.",
        suggestedActionKind: "none",
      };
    }

    if (err.code === "roster.shift.not_found") {
      return {
        title: "Shift not found",
        description: "The selected shift template does not exist or is not available in this branch.",
        suggestedActionKind: "none",
      };
    }

    if (err.code === "roster.default.not_found") {
      return {
        title: "No default shift set",
        description: "This branch does not have a default shift yet.",
        suggestedActionKind: "none",
      };
    }

    if (err.code === "roster.assignment.invalid_dates") {
      return {
        title: "Invalid assignment dates",
        description: "The assignment range is invalid. Check the start and end dates and try again.",
        suggestedActionKind: "none",
      };
    }

    if (err.code === "roster.assignment.overlap") {
      return {
        title: "Overlapping assignment",
        description: "This employee already has a shift assignment that overlaps with the selected dates.",
        suggestedActionKind: "none",
      };
    }

    if (err.code === "roster.override.invalid") {
      return {
        title: "Invalid override",
        description: "Check the override type and selected shift, then try again.",
        suggestedActionKind: "none",
      };
    }

    // ----- Payables -----
    if (err.code === "attendance.payable.invalid_range") {
      return {
        title: "Invalid date range",
        description: "The selected range is too large or the start date is after the end date.",
        suggestedActionKind: "none",
      };
    }

    if (err.code === "attendance.payable.calendar_missing") {
      return {
        title: "Work calendar missing",
        description: "A required work calendar is missing for one or more employees in this range. Configure the calendar, then recompute.",
        suggestedActionKind: "none",
      };
    }

    if (err.code === "attendance.payable.employee.not_found") {
      return {
        title: "Employee not found",
        description: "The selected employee does not exist or is not visible in the current scope.",
        suggestedActionKind: "none",
      };
    }

    if (err.code === "attendance.payable.recompute.forbidden") {
      return {
        title: "Recompute requires a target",
        description: "Select a branch or employee before recomputing payable days.",
        suggestedActionKind: "none",
      };
    }

    // ----- Workflow backbone -----
    if (err.code === "workflow.step.not_assignee") {
      return {
        title: "Not allowed",
        description: "You are not assigned to approve this request.",
        suggestedActionKind: "none",
      };
    }

    if (
      err.code === "workflow.request.not_pending" ||
      err.code === "workflow.step.not_pending" ||
      err.code === "workflow.step.already_decided"
    ) {
      return {
        title: "Already finalized",
        description: "This request is no longer pending. Refresh to see the latest status.",
        suggestedActionKind: "retry",
      };
    }

    // Participant-safe not-found (hide existence).
    if (err.code === "workflow.request.not_participant") {
      return {
        title: "Not found",
        description: "The requested workflow request does not exist or you do not have access.",
        suggestedActionKind: "none",
      };
    }

    if (err.code === "workflow.request.not_found") {
      return {
        title: "Not found",
        description: "The requested workflow request does not exist or you do not have access.",
        suggestedActionKind: "none",
      };
    }

    if (err.code === "workflow.request_type.not_found") {
      return {
        title: "Unknown request type",
        description: "This workflow request type does not exist. Contact an administrator.",
        suggestedActionKind: "none",
      };
    }

    if (err.code === "workflow.definition.not_found") {
      return {
        title: "Workflow definition not found",
        description: "This workflow definition is missing or invalid. Review the definition configuration and try again.",
        suggestedActionKind: "none",
      };
    }

    if (err.code === "workflow.no_assignees") {
      return {
        title: "No approvers configured",
        description: "No approvers could be resolved for this workflow. Contact an administrator.",
        suggestedActionKind: "none",
      };
    }

    if (err.code === "workflow.manager_missing") {
      return {
        title: "Manager not set",
        description: "This workflow requires a manager, but no manager is assigned. Contact HR for help.",
        suggestedActionKind: "none",
      };
    }

    // ----- DMS -----
    if (err.code === "dms.document.not_found") {
      return {
        title: "Not found",
        description: "The requested document does not exist or is not accessible.",
        suggestedActionKind: "none",
      };
    }

    if (err.code === "dms.document_type.not_found") {
      return {
        title: "Document type not found",
        description: "The selected document type is missing or inactive.",
        suggestedActionKind: "none",
      };
    }

    if (err.code === "dms.file.not_found") {
      return {
        title: "File not found",
        description: "The selected file does not exist or is not accessible.",
        suggestedActionKind: "none",
      };
    }

    if (err.code === "dms.file.not_ready") {
      return {
        title: "File not ready",
        description: "The uploaded file is still processing. Try again in a moment.",
        suggestedActionKind: "retry",
      };
    }

    if (err.code === "dms.document.verify.already_terminal") {
      return {
        title: "Verification already completed",
        description: "This document is already verified, rejected, or expired.",
        suggestedActionKind: "none",
      };
    }

    if (err.code === "dms.document.version.conflict") {
      return {
        title: "Document update conflict",
        description: "This document changed while you were editing it. Refresh and try again.",
        suggestedActionKind: "retry",
      };
    }

    if (err.code === "dms.expiry.rule.duplicate") {
      return {
        title: "Expiry rule already exists",
        description: "This document type already has an expiry rule for the selected window.",
        suggestedActionKind: "none",
      };
    }

    if (err.status === 404) {
      return {
        title: "Not found",
        description: "The requested resource does not exist or you do not have access.",
        suggestedActionKind: "none",
      };
    }

    if (err.status === 403 || err.code === "forbidden") {
      return {
        title: "Not allowed",
        description: "You do not have permission to perform this action.",
        suggestedActionKind: "none",
      };
    }

    if (err.status === 409) {
      return {
        title: "Conflict",
        description:
          "This request could not be completed due to a state conflict. Refresh and try again.",
        suggestedActionKind: "retry",
      };
    }

    return {
      title: "Request failed",
      description: err.message || "Something went wrong.",
      suggestedActionKind: "retry",
    };
  }

  if (err instanceof Error) {
    return {
      title: "Something went wrong",
      description: err.message || "Unexpected error.",
      suggestedActionKind: "retry",
    };
  }

  return {
    title: "Something went wrong",
    description: "Unexpected error.",
    suggestedActionKind: "retry",
  };
}
