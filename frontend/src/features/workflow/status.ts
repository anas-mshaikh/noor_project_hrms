export type WorkflowStatus =
  | "DRAFT"
  | "PENDING"
  | "APPROVED"
  | "REJECTED"
  | "CANCELED"
  | string;

export function workflowStatusLabel(status: string): string {
  const s = (status ?? "").toUpperCase();
  switch (s) {
    case "DRAFT":
      return "Draft";
    case "PENDING":
      return "Pending";
    case "APPROVED":
      return "Approved";
    case "REJECTED":
      return "Rejected";
    case "CANCELED":
    case "CANCELLED":
      return "Canceled";
    default:
      return s || "Unknown";
  }
}

/**
 * Backend `status` query param (outbox).
 *
 * The API currently accepts values like: pending/submitted/approved/rejected/canceled/draft.
 * We prefer "pending" for the UI even though it maps to db "submitted".
 */
export function workflowStatusParam(status: string): string {
  const s = (status ?? "").toUpperCase();
  switch (s) {
    case "PENDING":
      return "pending";
    case "APPROVED":
      return "approved";
    case "REJECTED":
      return "rejected";
    case "CANCELED":
    case "CANCELLED":
      return "canceled";
    case "DRAFT":
      return "draft";
    default:
      return (status ?? "").toLowerCase();
  }
}
