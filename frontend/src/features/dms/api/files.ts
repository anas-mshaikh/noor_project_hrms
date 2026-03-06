import { apiDownload, apiForm, apiJson } from "@/lib/api";
import type { DmsFileOut, UUID } from "@/lib/types";

/**
 * DMS Files API wrapper.
 *
 * Used by workflow attachments (upload -> attach -> download).
 */

export async function uploadFile(
  file: File,
  init?: RequestInit,
): Promise<DmsFileOut> {
  const form = new FormData();
  form.append("file", file);
  return apiForm<DmsFileOut>("/api/v1/dms/files", form, init);
}

export async function getFileMeta(
  fileId: UUID,
  init?: RequestInit,
): Promise<DmsFileOut> {
  return apiJson<DmsFileOut>(`/api/v1/dms/files/${fileId}`, init);
}

export async function downloadFile(
  fileId: UUID,
  init?: RequestInit & { filename?: string },
): Promise<{ filename: string; blob: Blob; contentType: string | null }> {
  return apiDownload(`/api/v1/dms/files/${fileId}/download`, init);
}
