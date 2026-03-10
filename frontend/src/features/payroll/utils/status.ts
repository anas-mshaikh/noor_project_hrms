export function payrollStatusLabel(status: string | null | undefined): string {
  switch ((status ?? "").toUpperCase()) {
    case "DRAFT":
      return "Draft";
    case "PENDING_APPROVAL":
      return "Pending approval";
    case "APPROVED":
      return "Approved";
    case "PUBLISHED":
      return "Published";
    case "CANCELED":
    case "CANCELLED":
      return "Canceled";
    default:
      return status || "Unknown";
  }
}

export function payrunAnomalyLabel(code: string): string {
  switch ((code ?? "").toUpperCase()) {
    case "NO_COMPENSATION":
      return "No compensation record";
    case "NO_PAYABLE_SUMMARIES":
      return "No payable summaries";
    case "CURRENCY_MISMATCH":
      return "Currency mismatch";
    default:
      return code.replace(/_/g, " ").toLowerCase();
  }
}
