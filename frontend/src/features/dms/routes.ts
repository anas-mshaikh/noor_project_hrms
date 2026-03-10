import type { UUID } from "@/lib/types";

export function employeeDocsHref(args?: {
  employeeId?: UUID | null;
  docId?: UUID | null;
}): string {
  const qs = new URLSearchParams();
  if (args?.employeeId) qs.set("employeeId", args.employeeId);
  if (args?.docId) qs.set("docId", args.docId);
  const query = qs.toString();
  return query ? `/dms/employee-docs?${query}` : "/dms/employee-docs";
}

export function myDocsHref(args?: { docId?: UUID | null }): string {
  const qs = new URLSearchParams();
  if (args?.docId) qs.set("docId", args.docId);
  const query = qs.toString();
  return query ? `/dms/my-docs?${query}` : "/dms/my-docs";
}

export function compatibilityDocHref(args: {
  docId: UUID;
  employeeId?: UUID | null;
}): string {
  const qs = new URLSearchParams();
  if (args.employeeId) qs.set("employeeId", args.employeeId);
  const query = qs.toString();
  return query ? `/dms/documents/${args.docId}?${query}` : `/dms/documents/${args.docId}`;
}
