import type { UUID } from "@/lib/types";

export const dmsKeys = {
  fileMeta: (fileId: UUID | null) => ["dms", "file-meta", fileId] as const,
};
