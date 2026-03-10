export function dmsStatusLabel(status: string): string {
  switch ((status ?? "").toUpperCase()) {
    case "DRAFT":
      return "Draft";
    case "SUBMITTED":
      return "Submitted";
    case "VERIFIED":
      return "Verified";
    case "REJECTED":
      return "Rejected";
    case "EXPIRED":
      return "Expired";
    default:
      return status || "Unknown";
  }
}
