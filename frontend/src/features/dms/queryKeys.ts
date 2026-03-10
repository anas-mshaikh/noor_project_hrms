import type { UUID } from "@/lib/types";

export const dmsKeys = {
  documentTypes: () => ["dms", "document-types"] as const,
  employeeDocs: (args: {
    employeeId: UUID | null;
    status?: string | null;
    type?: string | null;
    limit: number;
  }) =>
    [
      "dms",
      "employee-docs",
      args.employeeId,
      args.status ?? null,
      args.type ?? null,
      args.limit,
    ] as const,
  myDocs: (args: { status?: string | null; type?: string | null; limit: number }) =>
    ["dms", "my-docs", args.status ?? null, args.type ?? null, args.limit] as const,
  myDoc: (documentId: UUID | null) => ["dms", "my-doc", documentId] as const,
  expiryUpcoming: (days: number) => ["dms", "expiry", "upcoming", days] as const,
  expiryRules: () => ["dms", "expiry", "rules"] as const,
  fileMeta: (fileId: UUID | null) => ["dms", "file-meta", fileId] as const,
};
