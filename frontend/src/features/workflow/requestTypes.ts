export function workflowRequestTypeLabel(requestTypeCode: string): string {
  switch ((requestTypeCode ?? "").toUpperCase()) {
    case "DOCUMENT_VERIFICATION":
      return "Document verification";
    default:
      return requestTypeCode || "Request";
  }
}
