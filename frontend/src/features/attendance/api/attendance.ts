import { apiJson } from "@/lib/api";
import type {
  AttendanceCorrectionCreateIn,
  AttendanceCorrectionListOut,
  AttendanceCorrectionOut,
  AttendanceDaysOut,
  PunchStateOut,
  UUID,
} from "@/lib/types";

/**
 * Attendance API wrapper (ESS).
 */

export async function getPunchState(
  init?: RequestInit,
): Promise<PunchStateOut> {
  return apiJson<PunchStateOut>("/api/v1/attendance/me/punch-state", init);
}

export async function punchIn(
  payload: {
    idempotency_key?: string | null;
    meta?: Record<string, unknown> | null;
  },
  init?: RequestInit,
): Promise<PunchStateOut> {
  return apiJson<PunchStateOut>("/api/v1/attendance/me/punch-in", {
    method: "POST",
    body: JSON.stringify(payload ?? {}),
    ...init,
  });
}

export async function punchOut(
  payload: {
    idempotency_key?: string | null;
    meta?: Record<string, unknown> | null;
  },
  init?: RequestInit,
): Promise<PunchStateOut> {
  return apiJson<PunchStateOut>("/api/v1/attendance/me/punch-out", {
    method: "POST",
    body: JSON.stringify(payload ?? {}),
    ...init,
  });
}

export async function listMyDays(
  args: { from: string; to: string },
  init?: RequestInit,
): Promise<AttendanceDaysOut> {
  const qs = new URLSearchParams({ from: args.from, to: args.to });
  return apiJson<AttendanceDaysOut>(
    `/api/v1/attendance/me/days?${qs.toString()}`,
    init,
  );
}

export async function submitMyCorrection(
  payload: AttendanceCorrectionCreateIn,
  init?: RequestInit,
): Promise<AttendanceCorrectionOut> {
  return apiJson<AttendanceCorrectionOut>("/api/v1/attendance/me/corrections", {
    method: "POST",
    body: JSON.stringify(payload),
    ...init,
  });
}

export async function listMyCorrections(
  args: { status?: string | null; limit: number; cursor?: string | null },
  init?: RequestInit,
): Promise<AttendanceCorrectionListOut> {
  const qs = new URLSearchParams({ limit: String(args.limit) });
  if (args.status) qs.set("status", args.status);
  if (args.cursor) qs.set("cursor", args.cursor);
  return apiJson<AttendanceCorrectionListOut>(
    `/api/v1/attendance/me/corrections?${qs.toString()}`,
    init,
  );
}

export async function cancelMyCorrection(
  correctionId: UUID,
  init?: RequestInit,
): Promise<AttendanceCorrectionOut> {
  return apiJson<AttendanceCorrectionOut>(
    `/api/v1/attendance/me/corrections/${correctionId}/cancel`,
    {
      method: "POST",
      ...init,
    },
  );
}
