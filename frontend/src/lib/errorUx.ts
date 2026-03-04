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
