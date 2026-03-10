export function workflowRequestTypeLabel(requestTypeCode: string): string {
  switch ((requestTypeCode ?? "").toUpperCase()) {
    case "DOCUMENT_VERIFICATION":
      return "Document verification";
    case "PAYRUN_APPROVAL":
      return "Payrun approval";
    default:
      return requestTypeCode || "Request";
  }
}
